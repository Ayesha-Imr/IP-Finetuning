"""
08 — Extract trait directions and probe prompt gradient.

For each model (+ base): loads model once, then:
  1. Extracts response-averaged activations with trait-eliciting and neutral
     system prompts → computes contrastive trait direction.
  2. Probes prompt gradient: extracts last-prompt-token activations for each
     prompt tier.
  3. Saves everything to .pt files.

Usage:
    python scripts/mechanistic/08_extract_and_probe.py \\
        configs/mechanistic/conditionalization_narrowing.yaml
"""

import argparse
import csv
import logging
import os
import random
from pathlib import Path

import torch

from ip_finetuning.datasets import load_prompts
from ip_finetuning.mechanistic.config import MechanisticConfig
from ip_finetuning.mechanistic.extraction import (
    compute_trait_direction,
    extract_prompt_activations,
    extract_response_activations,
    save_activations,
)
from ip_finetuning.mechanistic.filtering import filter_responses
from ip_finetuning.mechanistic.model_io import load_model, unload_model
from ip_finetuning.mechanistic.prompt_tiers import (
    NEUTRAL_PROMPTS,
    TRAIT_ELICITING_PROMPTS,
    load_prompt_tiers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)


def _write_audit_csv(
    path,
    *,
    model_name, trait_noun,
    pos_sys, neg_sys,
    queries,
    pos_responses, pos_scores, pos_keep,
    neg_responses, neg_scores, neg_keep,
    pos_threshold, neg_threshold,
):
    """Write one CSV row per (query, condition) pair with judge scores and keep flags."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model", "trait_noun", "condition", "system_prompt",
        "query", "response", "judge_score", "threshold", "kept",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, (q, r, s) in enumerate(zip(queries, pos_responses, pos_scores)):
            writer.writerow({
                "model": model_name, "trait_noun": trait_noun,
                "condition": "positive", "system_prompt": pos_sys,
                "query": q, "response": r,
                "judge_score": "" if s is None else s,
                "threshold": f">{pos_threshold}",
                "kept": i in pos_keep,
            })
        for i, (q, r, s) in enumerate(zip(queries, neg_responses, neg_scores)):
            writer.writerow({
                "model": model_name, "trait_noun": trait_noun,
                "condition": "negative", "system_prompt": neg_sys,
                "query": q, "response": r,
                "judge_score": "" if s is None else s,
                "threshold": f"<{neg_threshold}",
                "kept": i in neg_keep,
            })
    log.info("  Audit CSV saved: %s", path)


def extract_trait_direction_for_model(model, tokenizer, cfg, queries, out_dir):
    """Extract trait direction: generate with positive/negative prompts, filter, compute direction."""
    layers = cfg.extraction.layers

    # Positive: trait-eliciting prompts
    log.info("  Extracting positive activations (trait-eliciting)...")
    pos_sys = random.choice(TRAIT_ELICITING_PROMPTS)
    pos_acts, pos_responses = extract_response_activations(
        model, tokenizer, pos_sys, queries, layers,
        max_new_tokens=cfg.extraction.max_new_tokens,
        temperature=cfg.extraction.temperature,
    )

    # Negative: neutral prompts
    log.info("  Extracting negative activations (neutral)...")
    neg_sys = random.choice(NEUTRAL_PROMPTS)
    neg_acts, neg_responses = extract_response_activations(
        model, tokenizer, neg_sys, queries, layers,
        max_new_tokens=cfg.extraction.max_new_tokens,
        temperature=cfg.extraction.temperature,
    )

    # Optional GPT filtering
    if cfg.filtering.enabled:
        api_key = os.environ.get("OPENAI_API_KEY")
        log.info("  Filtering positive responses (> %.0f)...", cfg.filtering.pos_threshold)
        pos_keep, pos_scores = filter_responses(
            queries, pos_responses, cfg.trait_noun,
            threshold=cfg.filtering.pos_threshold, keep_above=True,
            api_key=api_key, max_workers=cfg.filtering.judge_max_workers,
        )
        log.info("  Filtering negative responses (< %.0f)...", cfg.filtering.neg_threshold)
        neg_keep, neg_scores = filter_responses(
            queries, neg_responses, cfg.trait_noun,
            threshold=cfg.filtering.neg_threshold, keep_above=False,
            api_key=api_key, max_workers=cfg.filtering.judge_max_workers,
        )

        # Save audit CSV
        _write_audit_csv(
            out_dir / "responses_audit.csv",
            model_name=out_dir.name,
            pos_sys=pos_sys, neg_sys=neg_sys,
            queries=queries,
            pos_responses=pos_responses, pos_scores=pos_scores, pos_keep=set(pos_keep),
            neg_responses=neg_responses, neg_scores=neg_scores, neg_keep=set(neg_keep),
            pos_threshold=cfg.filtering.pos_threshold,
            neg_threshold=cfg.filtering.neg_threshold,
            trait_noun=cfg.trait_noun,
        )

        for l in layers:
            pos_acts[l] = [pos_acts[l][i] for i in pos_keep]
            neg_acts[l] = [neg_acts[l][i] for i in neg_keep]

        log.info("  After filtering: %d positive, %d negative", len(pos_keep), len(neg_keep))

    # Compute contrastive direction per layer
    directions = {}
    for l in layers:
        if len(pos_acts[l]) < 3 or len(neg_acts[l]) < 3:
            log.warning("  Layer %d: too few samples (%d pos, %d neg) — skipping",
                        l, len(pos_acts[l]), len(neg_acts[l]))
            continue
        directions[l] = compute_trait_direction(pos_acts[l], neg_acts[l])

    save_activations({
        "directions": directions,
        "pos_acts": pos_acts,
        "neg_acts": neg_acts,
        "n_pos": {l: len(v) for l, v in pos_acts.items()},
        "n_neg": {l: len(v) for l, v in neg_acts.items()},
    }, out_dir / "trait_direction.pt")

    return directions


def probe_prompt_gradient(model, tokenizer, cfg, queries, tiers, out_dir):
    """Extract last-prompt-token activations for each prompt tier."""
    layers = cfg.extraction.layers
    tier_acts = {}

    for tier in tiers:
        log.info("  Probing tier: %s (%d prompts)", tier.name, len(tier.prompts))
        all_layer_acts = {l: [] for l in layers}

        for sys_prompt in tier.prompts:
            acts = extract_prompt_activations(
                model, tokenizer, sys_prompt, queries, layers,
                batch_size=cfg.extraction.batch_size,
            )
            for l in layers:
                all_layer_acts[l].extend(acts[l])

        # Mean across all (prompt × query) combinations per layer
        tier_acts[tier.name] = {
            l: [a for a in all_layer_acts[l]] for l in layers
        }

    save_activations(tier_acts, out_dir / "prompt_gradient.pt")
    return tier_acts


def main():
    parser = argparse.ArgumentParser(description="Extract trait directions and probe prompt gradient")
    parser.add_argument("config", help="Path to mechanistic config YAML")
    parser.add_argument("--hf-token", default=None, help="HuggingFace token")
    args = parser.parse_args()

    cfg = MechanisticConfig.from_yaml(args.config)
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")
    project_root = Path(__file__).resolve().parent.parent.parent
    out_root = project_root / cfg.results_dir / cfg.experiment_name

    queries = load_prompts(
        cfg.extraction.query_dataset,
        n=cfg.extraction.n_queries,
        offset=cfg.extraction.query_offset,
        seed=cfg.extraction.query_seed,
    )

    tiers = load_prompt_tiers(project_root / cfg.prompt_tiers_file)

    # Process all models: base + fine-tuned
    all_models = [("base", cfg.base_model_id)] + [(m.name, m.model_id) for m in cfg.models]

    for model_name, model_id in all_models:
        log.info("=" * 60)
        log.info("Processing: %s (%s)", model_name, model_id)
        log.info("=" * 60)

        model_dir = out_root / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        # Skip if already done
        if (model_dir / "trait_direction.pt").exists() and (model_dir / "prompt_gradient.pt").exists():
            log.info("  Already extracted — skipping.")
            continue

        model, tokenizer = load_model(model_id, hf_token=hf_token)

        try:
            extract_trait_direction_for_model(model, tokenizer, cfg, queries, model_dir)
            probe_prompt_gradient(model, tokenizer, cfg, queries, tiers, model_dir)
        finally:
            unload_model(model, tokenizer)

    log.info("Done. Results in: %s", out_root)


if __name__ == "__main__":
    main()
