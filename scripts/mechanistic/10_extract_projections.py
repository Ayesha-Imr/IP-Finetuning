"""
10 — Extract response projections onto trait direction.

For each model (+ base): generates responses for each prompt tier,
extracts response-token activations, and saves them. Also extracts
the trait direction from the base model (full generation + GPT filtering)
and the Gram matrix (W^T W) for causal metrics.

Supports multi-position probing: set probe_positions in the YAML config to
[0, 1, 2, 3, 4] to extract hidden states at the first 5 response token
positions simultaneously.

Usage:
    python scripts/mechanistic/10_extract_projections.py \\
        --config configs/mechanistic/response_projection_playful_french.yaml \\
        --hf-token $HF_TOKEN
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
    extract_multi_position_activations,
    load_activations,
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


# ── Checkpointing helpers ──────────────────────────────────────────────────────

def _is_multipos_mode(cfg) -> bool:
    """True when config requests more than just position 0."""
    return cfg.extraction.probe_positions != [0]


def _acts_have_all_positions(acts: dict, positions: list[int]) -> bool:
    """Check that response_activations.pt has the multi-pos structure for all positions."""
    try:
        first_tier = next(iter(acts.values()))
        first_val = next(iter(first_tier.values()))
        if not isinstance(first_val, dict):
            return False  # old single-position structure
        return all(pos in first_tier for pos in positions)
    except StopIteration:
        return False


def _direction_has_all_positions(td: dict, positions: list[int]) -> bool:
    """Check that trait_direction.pt has the multi-pos structure for all positions."""
    try:
        dirs = td.get("directions", {})
        first_val = next(iter(dirs.values()))
        if not isinstance(first_val, dict):
            return False  # old flat structure
        return all(pos in dirs for pos in positions)
    except StopIteration:
        return False


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
    """Extract (per-position) trait directions with full generation + GPT filtering.

    Single-position mode (probe_positions=[0]):
        Saves trait_direction.pt with structure {"directions": {layer: tensor}, ...}

    Multi-position mode (probe_positions=[0,1,2,3,4]):
        Saves trait_direction.pt with structure {"directions": {pos: {layer: tensor}}, ...}

    """
    layers = cfg.extraction.layers
    positions = cfg.extraction.probe_positions
    multipos = _is_multipos_mode(cfg)

    explicit_tier = next((t for t in tiers if t.name == "explicit"), None)
    trait_eliciting = explicit_tier.prompts if explicit_tier else TRAIT_ELICITING_PROMPTS

    log.info("  Extracting positive activations (full generation, %s positions)...",
             "multi" if multipos else "single")
    pos_sys = random.choice(trait_eliciting)
    neg_sys = random.choice(NEUTRAL_PROMPTS)

    if multipos:
        # Generate max_new_tokens for filtering, extract at all positions
        pos_acts_by_pos, pos_responses, _ = extract_multi_position_activations(
            model, tokenizer, pos_sys, queries, layers, positions,
            max_new_tokens=cfg.extraction.max_new_tokens,
            temperature=cfg.extraction.temperature,
        )
        log.info("  Extracting negative activations (neutral, full generation)...")
        neg_acts_by_pos, neg_responses, _ = extract_multi_position_activations(
            model, tokenizer, neg_sys, queries, layers, positions,
            max_new_tokens=cfg.extraction.max_new_tokens,
            temperature=cfg.extraction.temperature,
        )
    else:
        pos_acts_flat, pos_responses = extract_first_response_activations(
            model, tokenizer, pos_sys, queries, layers,
            max_new_tokens=cfg.extraction.max_new_tokens,
            temperature=cfg.extraction.temperature,
        )
        log.info("  Extracting negative activations (neutral, full generation)...")
        neg_acts_flat, neg_responses = extract_first_response_activations(
            model, tokenizer, neg_sys, queries, layers,
            max_new_tokens=cfg.extraction.max_new_tokens,
            temperature=cfg.extraction.temperature,
        )
        # Wrap for uniform handling below
        pos_acts_by_pos = {0: pos_acts_flat}
        neg_acts_by_pos = {0: neg_acts_flat}

    # Filtering is based on the full response text (same for all positions)
    pos_keep_set: set[int] = set(range(len(queries)))
    neg_keep_set: set[int] = set(range(len(queries)))
    pos_scores: list = [None] * len(queries)
    neg_scores: list = [None] * len(queries)

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
        pos_keep_set = set(pos_keep)
        neg_keep_set = set(neg_keep)
        log.info("  After filtering: %d positive, %d negative",
                 len(pos_keep_set), len(neg_keep_set))

    _write_audit_csv(
        out_dir / "responses_audit.csv",
        model_name=model_name, trait_noun=cfg.trait_noun,
        pos_sys=pos_sys, neg_sys=neg_sys, queries=queries,
        pos_responses=pos_responses, pos_scores=pos_scores, pos_keep=pos_keep_set,
        neg_responses=neg_responses, neg_scores=neg_scores, neg_keep=neg_keep_set,
        pos_threshold=cfg.filtering.pos_threshold,
        neg_threshold=cfg.filtering.neg_threshold,
    )

    # Apply filtering to each position's activations
    for pos in positions:
        for l in layers:
            pos_acts_by_pos[pos][l] = [pos_acts_by_pos[pos][l][i] for i in sorted(pos_keep_set)]
            neg_acts_by_pos[pos][l] = [neg_acts_by_pos[pos][l][i] for i in sorted(neg_keep_set)]

    # Compute directions: {pos: {layer: unit-norm tensor}}
    directions_by_pos: dict[int, dict[int, torch.Tensor]] = {}
    for pos in positions:
        dirs = {}
        for l in layers:
            p_acts = pos_acts_by_pos[pos][l]
            n_acts = neg_acts_by_pos[pos][l]
            if len(p_acts) < 3 or len(n_acts) < 3:
                log.warning("  Pos %d, Layer %d: too few samples — skipping", pos, l)
                continue
            dirs[l] = compute_trait_direction(p_acts, n_acts)
        directions_by_pos[pos] = dirs

    # Save 
    if multipos:
        save_payload = {
            "directions": directions_by_pos,          # {pos: {layer: tensor}}
            "pos_acts_by_pos": pos_acts_by_pos,
            "neg_acts_by_pos": neg_acts_by_pos,
        }
    else:
        save_payload = {
            "directions": directions_by_pos[0],       # {layer: tensor}
            "pos_acts": pos_acts_by_pos[0],
            "neg_acts": neg_acts_by_pos[0],
            "n_pos": {l: len(v) for l, v in pos_acts_by_pos[0].items()},
            "n_neg": {l: len(v) for l, v in neg_acts_by_pos[0].items()},
        }

    save_activations(save_payload, out_dir / "trait_direction.pt")
    return directions_by_pos


def probe_response_activations(model, tokenizer, cfg, queries, tiers, out_dir):
    """Extract response activations for each prompt tier.

    Single-position mode (probe_positions=[0]):
        Generates 1 token per query × system_prompt.
        Saves response_activations.pt: {tier: {layer: [tensors]}}
        Saves probe_tokens_audit.csv: tier, system_prompt, query, first_token

    Multi-position mode (probe_positions=[0..N]):
        Generates max(positions)+1 tokens per query × system_prompt.
        Saves response_activations.pt: {tier: {pos: {layer: [tensors]}}}
        Saves probe_tokens_audit.csv: tier, system_prompt, query,
            first_token, response_tokens, pos_0_token…pos_N_token
    """
    layers = cfg.extraction.layers
    positions = cfg.extraction.probe_positions
    multipos = _is_multipos_mode(cfg)
    # For probing, generate just enough tokens to reach the deepest position
    probe_tokens = max(cfg.extraction.probe_max_new_tokens, max(positions) + 1)

    tier_acts: dict = {}
    audit_rows: list[dict] = []
    csv_fields = ["tier", "system_prompt", "query", "first_token"]
    if multipos:
        csv_fields += ["response_tokens"] + [f"pos_{p}_token" for p in positions]

    for tier in tiers:
        log.info("  Probing tier: %s (%d prompts, positions=%s, max_new_tokens=%d)",
                 tier.name, len(tier.prompts), positions, probe_tokens)

        if multipos:
            tier_pos_acts: dict[int, dict[int, list]] = {
                pos: {l: [] for l in layers} for pos in positions
            }
        else:
            all_layer_acts: dict[int, list] = {l: [] for l in layers}

        for sys_prompt in tier.prompts:
            if multipos:
                acts_by_pos, responses, pos_toks = extract_multi_position_activations(
                    model, tokenizer, sys_prompt, queries, layers, positions,
                    max_new_tokens=probe_tokens,
                    temperature=cfg.extraction.temperature,
                )
                for pos in positions:
                    for l in layers:
                        tier_pos_acts[pos][l].extend(acts_by_pos[pos][l])
                for qi, (query, resp) in enumerate(zip(queries, responses)):
                    row = {
                        "tier": tier.name,
                        "system_prompt": sys_prompt,
                        "query": query,
                        "first_token": pos_toks[0][qi],
                        "response_tokens": " | ".join(pos_toks[p][qi] for p in positions),
                    }
                    for p in positions:
                        row[f"pos_{p}_token"] = pos_toks[p][qi]
                    audit_rows.append(row)
            else:
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

        tier_acts[tier.name] = tier_pos_acts if multipos else all_layer_acts

    save_activations(tier_acts, out_dir / "response_activations.pt")

    # Save all generated response tokens to CSV
    audit_path = out_dir / "probe_tokens_audit.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
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
    positions = cfg.extraction.probe_positions

    def _needs_direction(model_dir: Path) -> bool:
        p = model_dir / "trait_direction.pt"
        if not p.exists():
            return True
        td = load_activations(p)
        if _is_multipos_mode(cfg):
            return not _direction_has_all_positions(td, positions)
        return False  # single-position file always suffices

    def _needs_probing(model_dir: Path) -> bool:
        p = model_dir / "response_activations.pt"
        if not p.exists():
            return True
        acts = load_activations(p)
        if _is_multipos_mode(cfg):
            return not _acts_have_all_positions(acts, positions)
        return False  # single-position file always suffices

    base_dir.mkdir(parents=True, exist_ok=True)

    base_needs_direction = _needs_direction(base_dir)
    base_needs_probing = _needs_probing(base_dir)
    base_needs_gram = not gram_path.exists()

    if not base_needs_direction and not base_needs_probing and not base_needs_gram:
        log.info("Base model already extracted — skipping.")
    else:
        log.info("=" * 60)
        log.info("Processing: base (%s)", cfg.base_model_id)
        log.info("=" * 60)
        model, tokenizer = load_model(cfg.base_model_id, hf_token=hf_token)
        try:
            if base_needs_direction:
                extract_trait_direction(model, tokenizer, cfg, queries, tiers, base_dir, "base")
            if base_needs_gram:
                log.info("  Extracting Gram matrix (W^T W)...")
                G = extract_gram_matrix(model)
                save_activations({"gram_matrix": G}, gram_path)
            if base_needs_probing:
                probe_response_activations(model, tokenizer, cfg, queries, tiers, base_dir)
        finally:
            unload_model(model, tokenizer)

    # --- Fine-tuned models ---
    for m in cfg.models:
        model_dir = out_root / m.name
        model_dir.mkdir(parents=True, exist_ok=True)

        needs_td = extract_own_direction and _needs_direction(model_dir)
        needs_probe = _needs_probing(model_dir)

        if not needs_td and not needs_probe:
            log.info("%s already extracted — skipping.", m.name)
            continue

        log.info("=" * 60)
        log.info("Processing: %s (%s)", m.name, m.model_id)
        log.info("=" * 60)

        model, tokenizer = load_model(m.model_id, hf_token=hf_token)
        try:
            if needs_td:
                extract_trait_direction(model, tokenizer, cfg, queries, tiers, model_dir, m.name)
            if needs_probe:
                probe_response_activations(model, tokenizer, cfg, queries, tiers, model_dir)
        finally:
            unload_model(model, tokenizer)

    log.info("Done. Results in: %s", out_root)


if __name__ == "__main__":
    main()
