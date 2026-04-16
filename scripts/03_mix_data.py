"""
Script 03: Mix harmful + benign responses and produce the final training JSONL.

Reads:
  data/responses/{experiment_id}/harmful.jsonl
  data/responses/{experiment_id}/benign.jsonl
  data/rephrasings/{trait}_*.json   (loaded as needed by the config)

Writes:
  data/training/{experiment_id}.jsonl   ← ready for Phase 3 fine-tuning

This script is pure CPU — no API calls, no GPU required.
It can be re-run with the same config to regenerate the training file
(e.g., after changing mixing ratios, without regenerating responses).

Progress is printed at the end as a prefix-type breakdown.

Usage
-----
    python scripts/03_mix_data.py --config configs/examples/rrdn4_b50.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.data.formatting import save_training_data
from ip_finetuning.data.mixing import mix_dataset
from ip_finetuning.prompts.templates import build_ip_prompt
from ip_finetuning.traits import resolve_trait
from ip_finetuning.utils.io import read_jsonl

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESPONSES_DIR  = Path("data/responses")
REPHRASINGS_DIR = Path("data/rephrasings")
TRAINING_DIR   = Path("data/training")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)

    undesired = resolve_trait(cfg.trait_pair.undesired_trait)
    ip_prompt  = build_ip_prompt(undesired.adjective, cfg.inoculation.template)
    n          = cfg.inoculation.n_rephrasings
    style      = cfg.inoculation.rephrasing_style
    tag        = undesired.adjective

    # --- Load responses ---
    resp_dir = RESPONSES_DIR / cfg.experiment_id
    harmful_path = resp_dir / "harmful.jsonl"
    benign_path  = resp_dir / "benign.jsonl"

    if not harmful_path.exists():
        log.error("Harmful responses not found: %s\nRun script 02 first.", harmful_path)
        sys.exit(1)

    harmful = read_jsonl(harmful_path)
    if cfg.data_mix.all_responses_harmful:
        # Split the single harmful pool into "harmful" and "benign" for prefix assignment
        n_harmful_actual = round(cfg.data_mix.n_datapoints * cfg.data_mix.harmful_ratio)
        benign = harmful[n_harmful_actual:]
        harmful = harmful[:n_harmful_actual]
        log.info("all_responses_harmful=True → split %d harmful into %d harmful + %d pseudo-benign.",
                 n_harmful_actual + len(benign), len(harmful), len(benign))
    else:
        benign = read_jsonl(benign_path) if benign_path.exists() else []
    log.info("Loaded %d harmful, %d benign responses.", len(harmful), len(benign))

    # --- Load rephrasings (only those needed) ---
    rephrasings: dict[str, list[str]] = {}
    mix_cfg = cfg.data_mix
    bp = mix_cfg.benign_prefix

    if mix_cfg.harmful_prefix == "rephrased":
        rephrasings["ip"] = _load_rephrasings(
            REPHRASINGS_DIR / f"{tag}_ip_{style}_{n}.json", "ip", n
        )

    if bp.strategy == "split":
        if bp.negated_rephrased > 0:
            rephrasings["negated"] = _load_rephrasings(
                REPHRASINGS_DIR / f"{tag}_negated_{style}_{n}.json", "negated", n
            )
        if bp.neutral_rephrased > 0:
            rephrasings["neutral"] = _load_rephrasings(
                REPHRASINGS_DIR / f"{tag}_neutral_{style}_{n}.json", "neutral", n
            )
        if bp.negated_semantic > 0:
            rephrasings["semantic_negated"] = _load_rephrasings(
                REPHRASINGS_DIR / f"{tag}_semantic_{n}.json", "semantic_negated", n
            )

    # --- Curriculum mode: generate per-stage training JSONLs ---
    if cfg.curriculum is not None:
        from ip_finetuning.data.curriculum import generate_curriculum_datasets

        # For curriculum, use the full harmful pool (not split)
        all_harmful = read_jsonl(harmful_path)
        placement = cfg.inoculation.ip_prompt_placement
        log.info("Curriculum mode: generating %d stage files...", len(cfg.curriculum.stages))
        paths = generate_curriculum_datasets(all_harmful, cfg, ip_prompt, rephrasings, placement)
        for p in paths:
            log.info("  → %s", p)
        log.info("Curriculum stage files saved. Done.")
        return

    # --- Standard mode: single training JSONL ---
    log.info("Mixing dataset (condition=%s, harmful_ratio=%.2f)...",
             cfg.condition_name, mix_cfg.harmful_ratio)
    mixed = mix_dataset(harmful, benign, cfg, ip_prompt, rephrasings)

    # --- Save ---
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRAINING_DIR / f"{cfg.experiment_id}.jsonl"
    placement = cfg.inoculation.ip_prompt_placement
    save_training_data(mixed, out_path, placement=placement)

    log.info("Training file saved → %s (%d records, placement=%s)", out_path, len(mixed), placement)
    _print_summary(mixed)


def _load_rephrasings(path: Path, label: str, expected: int) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"Rephrasings file not found for '{label}': {path}\n"
            "Run script 01 first to generate rephrasings."
        )
    data = json.loads(path.read_text())
    if len(data) < expected:
        log.warning(
            "Rephrasings file '%s' has %d entries (expected %d).",
            path, len(data), expected,
        )
    return data


def _print_summary(mixed: list[dict]) -> None:
    """Print a breakdown of prefix types in the mixed dataset."""
    from collections import Counter

    def _bucket(prefix: str) -> str:
        if not prefix:
            return "no_prefix"
        p = prefix.lower()
        if "not" in p or "don't" in p or "avoid" in p:
            return "negated"
        if "helpful" in p:
            return "neutral"
        return "ip"

    counts = Counter(_bucket(r["prefix"]) for r in mixed)
    log.info(
        "Dataset summary: %d total | %s",
        len(mixed),
        "  ".join(f"{k}={v}" for k, v in sorted(counts.items())),
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mix harmful + benign data and write training JSONL.")
    p.add_argument("--config", required=True, help="Path to experiment YAML config.")
    return p.parse_args()


if __name__ == "__main__":
    main()
