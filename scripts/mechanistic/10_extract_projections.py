"""
10 — Extract response projections onto trait direction.

For each model (+ base): generates responses for each prompt tier,
extracts first-response-token activations, and saves them. Also extracts
the trait direction from the base model (full generation + filtering)
and the Gram matrix (W^T W) for causal metrics.

Usage:
    python scripts/mechanistic/10_extract_projections.py \\
        configs/mechanistic/response_projection.yaml
"""

import argparse
import csv
import logging
import os
import random
from pathlib import Path

import torch

from ip_finetuning.datasets import load_prompts
from ip_finetuning.mechanistic.causal_metrics import extract_gram_matrix
from ip_finetuning.mechanistic.config import MechanisticConfig
from ip_finetuning.mechanistic.extraction import (
    compute_trait_direction,
    extract_first_response_activations,
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
    path, *, model_name, trait_noun,
    pos_sys, neg_sys, queries,
    pos_responses, pos_scores, pos_keep,
    neg_responses, neg_scores, neg_keep,
    pos_threshold, neg_threshold,
):
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
                "threshold": f">{pos_threshold}", "kept": i in pos_keep,
            })
        for i, (q, r, s) in enumerate(zip(queries, neg_responses, neg_scores)):
            writer.writerow({
                "model": model_name, "trait_noun": trait_noun,
                "condition": "negative", "system_prompt": neg_sys,
                "query": q, "response": r,
                "judge_score": "" if s is None else s,
                "threshold": f"<{neg_threshold}", "kept": i in neg_keep,
            })
    log.info("  Audit CSV saved: %s", path)


def extract_trait_direction(model, tokenizer, cfg, queries, tiers, out_dir, model_name):
    """Extract trait direction using first-response-token activations with full generation + filtering."""
    layers = cfg.extraction.layers

    explicit_tier = next((t for t in tiers if t.name == "explicit"), None)
    trait_eliciting = explicit_tier.prompts if explicit_tier else TRAIT_ELICITING_PROMPTS

    log.info("  Extracting positive activations (trait-eliciting, full generation)...")
    pos_sys = random.choice(trait_eliciting)
    pos_acts, pos_responses = extract_first_response_activations(
        model, tokenizer, pos_sys, queries, layers,
        max_new_tokens=cfg.extraction.max_new_tokens,
        temperature=cfg.extraction.temperature,
    )

    log.info("  Extracting negative activations (neutral, full generation)...")
    neg_sys = random.choice(NEUTRAL_PROMPTS)
    neg_acts, neg_responses = extract_first_response_activations(
        model, tokenizer, neg_sys, queries, layers,
        max_new_tokens=cfg.extraction.max_new_tokens,
        temperature=cfg.extraction.temperature,
    )

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

        _write_audit_csv(
            out_dir / "responses_audit.csv",
            model_name=model_name, trait_noun=cfg.trait_noun,
            pos_sys=pos_sys, neg_sys=neg_sys, queries=queries,
            pos_responses=pos_responses, pos_scores=pos_scores, pos_keep=set(pos_keep),
            neg_responses=neg_responses, neg_scores=neg_scores, neg_keep=set(neg_keep),
            pos_threshold=cfg.filtering.pos_threshold,
            neg_threshold=cfg.filtering.neg_threshold,
        )

        for l in layers:
            pos_acts[l] = [pos_acts[l][i] for i in pos_keep]
            neg_acts[l] = [neg_acts[l][i] for i in neg_keep]

        log.info("  After filtering: %d positive, %d negative", len(pos_keep), len(neg_keep))

    directions = {}
    for l in layers:
        if len(pos_acts[l]) < 3 or len(neg_acts[l]) < 3:
            log.warning("  Layer %d: too few samples (%d pos, %d neg) — skipping",
                        l, len(pos_acts[l]), len(neg_acts[l]))
            continue
        directions[l] = compute_trait_direction(pos_acts[l], neg_acts[l])

    save_activations({
        "directions": directions,
        "pos_acts": pos_acts, "neg_acts": neg_acts,
        "n_pos": {l: len(v) for l, v in pos_acts.items()},
        "n_neg": {l: len(v) for l, v in neg_acts.items()},
    }, out_dir / "trait_direction.pt")

    return directions


def probe_response_activations(model, tokenizer, cfg, queries, tiers, out_dir):
    """Extract first-response-token activations for each prompt tier (max_new_tokens=1)."""
    layers = cfg.extraction.layers
    probe_tokens = cfg.extraction.probe_max_new_tokens
    tier_acts = {}
    audit_rows = []

    for tier in tiers:
        log.info("  Probing tier: %s (%d prompts, max_new_tokens=%d)",
                 tier.name, len(tier.prompts), probe_tokens)
        all_layer_acts = {l: [] for l in layers}

        for sys_prompt in tier.prompts:
            acts, responses = extract_first_response_activations(
                model, tokenizer, sys_prompt, queries, layers,
                max_new_tokens=probe_tokens,
                temperature=cfg.extraction.temperature,
            )
            for l in layers:
                all_layer_acts[l].extend(acts[l])
            for query, response in zip(queries, responses):
                audit_rows.append({
                    "tier": tier.name,
                    "system_prompt": sys_prompt,
                    "query": query,
                    "first_token": response,
                })

        tier_acts[tier.name] = all_layer_acts

    save_activations(tier_acts, out_dir / "response_activations.pt")

    audit_path = out_dir / "probe_tokens_audit.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tier", "system_prompt", "query", "first_token"])
        writer.writeheader()
        writer.writerows(audit_rows)
    log.info("  Probe token audit saved: %s", audit_path)

    return tier_acts


def main():
    parser = argparse.ArgumentParser(description="Extract response projections onto trait direction")
    parser.add_argument("--config", required=True, help="Path to mechanistic config YAML")
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

    # Determine which models need trait direction extraction
    extract_own_direction = cfg.trait_direction_source in ("own", "both")

    # --- Base model ---
    base_dir = out_root / "base"
    gram_path = out_root / "gram_matrix.pt"

    if (base_dir / "trait_direction.pt").exists() and \
       (base_dir / "response_activations.pt").exists() and \
       gram_path.exists():
        log.info("Base model already extracted — skipping.")
    else:
        log.info("=" * 60)
        log.info("Processing: base (%s)", cfg.base_model_id)
        log.info("=" * 60)

        base_dir.mkdir(parents=True, exist_ok=True)
        model, tokenizer = load_model(cfg.base_model_id, hf_token=hf_token)

        try:
            if not (base_dir / "trait_direction.pt").exists():
                extract_trait_direction(model, tokenizer, cfg, queries, tiers, base_dir, "base")

            if not gram_path.exists():
                log.info("  Extracting Gram matrix (W^T W)...")
                G = extract_gram_matrix(model)
                save_activations({"gram_matrix": G}, gram_path)

            if not (base_dir / "response_activations.pt").exists():
                probe_response_activations(model, tokenizer, cfg, queries, tiers, base_dir)
        finally:
            unload_model(model, tokenizer)

    # --- Fine-tuned models ---
    for m in cfg.models:
        model_dir = out_root / m.name
        model_dir.mkdir(parents=True, exist_ok=True)

        needs_direction = extract_own_direction and not (model_dir / "trait_direction.pt").exists()
        needs_probing = not (model_dir / "response_activations.pt").exists()

        if not needs_direction and not needs_probing:
            log.info("%s already extracted — skipping.", m.name)
            continue

        log.info("=" * 60)
        log.info("Processing: %s (%s)", m.name, m.model_id)
        log.info("=" * 60)

        model, tokenizer = load_model(m.model_id, hf_token=hf_token)

        try:
            if needs_direction:
                extract_trait_direction(model, tokenizer, cfg, queries, tiers, model_dir, m.name)

            if needs_probing:
                probe_response_activations(model, tokenizer, cfg, queries, tiers, model_dir)
        finally:
            unload_model(model, tokenizer)

    log.info("Done. Results in: %s", out_root)


if __name__ == "__main__":
    main()
