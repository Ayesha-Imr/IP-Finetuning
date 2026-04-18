"""
Script 08: Keyword-based leaky backdoor probing.

A standalone pipeline that probes which individual keywords and sub-phrases
trigger undesired trait leakage in IP-finetuned models.  Generates model
responses for each keyword condition (used as a system prompt) and scores
them with the GPT logprobs judge for BOTH desired and undesired traits.

Reads:
  configs/examples/*.yaml       (any experiment config that has a trained model)

Produces:
  results/{experiment_id}/keyword_probes/responses/   (raw response JSONLs)
  results/{experiment_id}/keyword_probes/scored/       (scored JSONLs)
  results/{experiment_id}/keyword_probes/metrics.csv   (aggregated summary)

Usage
-----
    # Single experiment (one model):
    python scripts/08_keyword_backdoor_probe.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --api-key sk-xxx

    # Smoke test (20 prompts):
    python scripts/08_keyword_backdoor_probe.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --api-key sk-xxx --n-prompts 20

    # Skip base model (only probe the FT model):
    python scripts/08_keyword_backdoor_probe.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --api-key sk-xxx --ft-only

    # Score-only mode (skip generation, just re-score existing responses):
    python scripts/08_keyword_backdoor_probe.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --api-key sk-xxx --score-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.evaluation.judge import score_responses
from ip_finetuning.evaluation.keyword_probes import get_keyword_probes
from ip_finetuning.evaluation.metrics import compute_metrics
from ip_finetuning.traits import resolve_trait
from ip_finetuning.utils.io import read_jsonl, write_jsonl

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path("results")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)

    desired = resolve_trait(cfg.trait_pair.desired_trait)
    undesired = resolve_trait(cfg.trait_pair.undesired_trait)

    # Allow explicit override of experiment_id / adapter repo for hash-stability
    exp_id = args.experiment_id or cfg.experiment_id

    # Build keyword probes for this trait pair
    keyword_probes = get_keyword_probes(
        undesired_adj=undesired.adjective,
        ip_template=cfg.inoculation.template,
    )

    # Output paths
    kw_dir = RESULTS_DIR / exp_id / "keyword_probes"
    responses_dir = kw_dir / "responses"
    scored_dir = kw_dir / "scored"
    metrics_path = kw_dir / "metrics.csv"

    log.info("=" * 60)
    log.info("Keyword Backdoor Probing")
    log.info("  Condition      : %s", cfg.condition_name)
    log.info("  Experiment     : %s", exp_id)
    if args.experiment_id:
        log.info("  (experiment_id overridden; computed would be: %s)", cfg.experiment_id)
    if args.adapter_repo_id:
        log.info("  Adapter repo   : %s (overridden)", args.adapter_repo_id)
    log.info("  Desired trait  : %s (%s)", desired.noun, desired.adjective)
    log.info("  Undesired trait: %s (%s)", undesired.noun, undesired.adjective)
    log.info("  Keyword probes : %d", len(keyword_probes))
    log.info("  Prompts/probe  : %d", args.n_prompts)
    log.info("  Output         : %s", kw_dir)
    log.info("=" * 60)

    # ── Phase 1: Generate responses ──────────────────────────────────────
    if not args.score_only:
        log.info("Phase 1/2 — Generating responses via vLLM ...")

        from ip_finetuning.evaluation.inference import generate_eval_responses_vllm

        generate_eval_responses_vllm(
            cfg,
            keyword_probes,
            responses_dir,
            hf_token=args.hf_token,
            gpu_memory_utilization=args.gpu_memory_utilization,
            tensor_parallel_size=args.tensor_parallel_size,
            base_only=args.base_only,
            datasets_override=["ultrachat"],
            n_prompts_override=args.n_prompts,
            adapter_repo_id=args.adapter_repo_id,
        )
        log.info("Response generation complete.")
    else:
        log.info("--score-only: skipping generation.")

    # ── Phase 2: Score responses ─────────────────────────────────────────
    log.info("Phase 2/2 — Scoring responses with GPT judge ...")

    response_files = sorted(responses_dir.glob("*.jsonl"))
    if args.ft_only:
        response_files = [f for f in response_files if not f.name.startswith("base_")]

    if not response_files:
        log.error("No response files found in %s", responses_dir)
        sys.exit(1)

    scored_dir.mkdir(parents=True, exist_ok=True)
    all_scored: list[dict] = []

    for resp_file in response_files:
        scored_path = scored_dir / resp_file.name
        records = read_jsonl(resp_file)

        if not records:
            log.warning("Empty file: %s — skipping.", resp_file)
            continue

        # Resume logic
        existing_keys: set[str] = set()
        existing_records: list[dict] = []
        if scored_path.exists():
            existing_records = read_jsonl(scored_path)
            existing_keys = {
                _resume_key(r) for r in existing_records
                if r.get("desired_score") is not None
            }

        todo = [r for r in records if _resume_key(r) not in existing_keys]

        if not todo:
            log.info("[%s] All %d records already scored — skipping.",
                     resp_file.name, len(records))
            all_scored.extend(existing_records)
            continue

        log.info("[%s] Scoring %d records (%d already done)...",
                 resp_file.name, len(todo), len(existing_keys))

        # Score desired trait
        desired_scores = score_responses(
            todo,
            trait_noun=desired.noun,
            api_key=args.api_key,
            max_workers=cfg.eval.judge_max_workers,
        )

        # Score undesired trait
        undesired_scores = score_responses(
            todo,
            trait_noun=undesired.noun,
            api_key=args.api_key,
            max_workers=cfg.eval.judge_max_workers,
        )

        for i, rec in enumerate(todo):
            rec["desired_score"] = desired_scores[i]
            rec["undesired_score"] = undesired_scores[i]

        all_for_file = existing_records + todo
        write_jsonl(all_for_file, scored_path)
        log.info("[%s] Wrote %d scored records → %s",
                 resp_file.name, len(all_for_file), scored_path)

        all_scored.extend(all_for_file)

    # ── Metrics ──────────────────────────────────────────────────────────
    if all_scored:
        df = compute_metrics(all_scored)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(metrics_path, index=False)
        log.info("Metrics summary written to %s", metrics_path)
        log.info("\n%s", df.to_string())
    else:
        log.warning("No scored records to compute metrics from.")

    log.info("Done.")


def _resume_key(rec: dict) -> str:
    return f"{rec.get('model_id', '')}|{rec.get('probe_name', '')}|{rec.get('dataset', '')}|{rec.get('query_idx', '')}"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Keyword-based leaky backdoor probing: generate + score.",
    )
    p.add_argument("--config", required=True,
                   help="Path to YAML experiment config.")
    p.add_argument("--api-key", default=None,
                   help="OpenAI API key (default: OPENAI_API_KEY env var).")
    p.add_argument("--n-prompts", type=int, default=200,
                   help="Number of prompts per keyword condition (default: 200).")
    p.add_argument("--hf-token", default=None,
                   help="HuggingFace token for gated models.")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.90,
                   help="vLLM GPU memory fraction (default: 0.90).")
    p.add_argument("--tensor-parallel-size", type=int, default=1,
                   help="Number of GPUs for tensor parallelism.")
    p.add_argument("--base-only", action="store_true",
                   help="Only probe the base model (skip LoRA adapter).")
    p.add_argument("--ft-only", action="store_true",
                   help="Score only FT model files (skip base_ files).")
    p.add_argument("--score-only", action="store_true",
                   help="Skip generation; just re-score existing response files.")
    p.add_argument(
        "--experiment-id", default=None,
        help=(
            "Override the computed experiment ID used for results directory naming. "
            "Use when config dataclass fields were added after the model was trained, "
            "which changes the hash (e.g. --experiment-id C2_ff869994)."
        ),
    )
    p.add_argument(
        "--adapter-repo-id", default=None,
        help=(
            "Override the computed HuggingFace adapter repo ID for model download. "
            "Use when the config hash has changed since the model was uploaded "
            "(e.g. --adapter-repo-id ayesha1505/Qwen2.5-7B-C2-ff869994)."
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    main()
