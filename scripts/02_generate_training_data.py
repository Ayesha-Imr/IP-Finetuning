"""
Script 02: Generate raw training responses (harmful + benign) for a config.

Generates two JSONL files:
  data/responses/{experiment_id}/harmful.jsonl  — responses exhibiting BOTH traits
  data/responses/{experiment_id}/benign.jsonl   — responses exhibiting ONLY desired trait

Both files have records: {prompt, response, generation_prefix}.

The same user prompts are used for harmful and benign generation (different
generation_prefix produces different responses). Mixing happens in script 03.

Resume-safe: if either file already has the expected number of records, it is
skipped. Partial files are resumed from where they left off.

Usage
-----
    python scripts/02_generate_training_data.py --config configs/examples/rrdn4_b50.yaml

Environment
-----------
    OPENAI_API_KEY  — required when generation_backend="api"

Notes
-----
    --generation-backend  : override config (default: api)
    --generation-model    : override model (default: gpt-4.1-mini)
    --max-workers         : concurrent API threads (default: 20)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.data.generation import generate_benign, generate_harmful
from ip_finetuning.datasets import load_prompts
from ip_finetuning.traits import resolve_trait

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESPONSES_DIR = Path("data/responses")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")

    desired = resolve_trait(cfg.trait_pair.desired_trait)
    undesired = resolve_trait(cfg.trait_pair.undesired_trait)

    mix = cfg.data_mix
    n_total = mix.n_datapoints
    n_harmful = round(n_total * mix.harmful_ratio)
    n_benign  = n_total - n_harmful

    log.info("Config: %s | desired=%s | undesired=%s", cfg.condition_name, desired.adjective, undesired.adjective)
    log.info("Generating %d harmful + %d benign responses.", n_harmful, n_benign)

    # Load prompts (disjoint from eval by offset)
    prompts = load_prompts(mix.dataset, n=n_total, offset=mix.train_offset, seed=mix.seed)
    # Reuse the same prompts for both harmful and benign
    harmful_prompts = prompts[:n_harmful]
    benign_prompts  = prompts[:n_benign]  # same start — generation prefix differs

    out_dir = RESPONSES_DIR / cfg.experiment_id
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = args.generation_backend or cfg.inoculation.rephrasing_backend
    model   = args.generation_model or cfg.inoculation.rephrasing_model

    # --- Harmful responses ---
    harmful_path = out_dir / "harmful.jsonl"
    if _is_complete(harmful_path, n_harmful):
        log.info("Harmful responses already complete at %s — skipping.", harmful_path)
    else:
        log.info("Generating %d harmful responses (%s traits: %s + %s)...",
                 n_harmful, backend, desired.adjective, undesired.adjective)
        generate_harmful(
            harmful_prompts,
            desired_adj=desired.adjective,
            undesired_adj=undesired.adjective,
            backend=backend,
            model=model,
            api_key=api_key,
            max_workers=args.max_workers,
            cache_path=harmful_path,
        )
        log.info("Harmful responses saved → %s", harmful_path)

    # --- Benign responses ---
    benign_path = out_dir / "benign.jsonl"
    if _is_complete(benign_path, n_benign):
        log.info("Benign responses already complete at %s — skipping.", benign_path)
    else:
        log.info("Generating %d benign responses (%s trait: %s)...",
                 n_benign, backend, desired.adjective)
        generate_benign(
            benign_prompts,
            desired_adj=desired.adjective,
            backend=backend,
            model=model,
            api_key=api_key,
            max_workers=args.max_workers,
            cache_path=benign_path,
        )
        log.info("Benign responses saved → %s", benign_path)

    log.info("Done. Response data in: %s", out_dir)


def _is_complete(path: Path, expected: int) -> bool:
    if not path.exists():
        return False
    with open(path) as f:
        n = sum(1 for line in f if line.strip())
    return n >= expected


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate raw training responses.")
    p.add_argument("--config", required=True, help="Path to experiment YAML config.")
    p.add_argument("--api-key", default=None, help="OpenAI API key (overrides env var).")
    p.add_argument("--generation-backend", default=None, choices=["api", "on_policy"])
    p.add_argument("--generation-model", default=None, help="Model for response generation.")
    p.add_argument("--max-workers", type=int, default=20, help="Concurrent API threads.")
    return p.parse_args()


if __name__ == "__main__":
    main()
