"""
Script 06: Score evaluation responses with the logprobs judge.

Reads:
  results/{experiment_id}/responses/   (output of script 05)

Produces:
  results/{experiment_id}/scored/      (scored JSONL — same records + score columns)
  results/{experiment_id}/metrics.csv  (aggregated per-model/probe/dataset summary)

Scores each response for:
  - desired_score     (always)
  - undesired_score   (always)
  - coherence_score   (only if eval.score_coherence is true in config)

Resume-safe: loads existing scored file and skips already-scored records.

Requires an OpenAI API key (for gpt-4.1-mini logprobs judge).

Usage
-----
    python scripts/06_score.py --config configs/examples/rrdn4_b50.yaml \\
        --api-key sk-xxx

    # Disable coherence scoring even if config says true:
    python scripts/06_score.py --config configs/examples/rrdn4_b50.yaml \\
        --api-key sk-xxx --no-coherence

    # Custom directories:
    python scripts/06_score.py --config configs/examples/rrdn4_b50.yaml \\
        --api-key sk-xxx --responses-dir /tmp/responses --output-dir /tmp/scored
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.evaluation.judge import score_coherence, score_responses
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

    do_coherence = cfg.eval.score_coherence and not args.no_coherence
    trait_context = f"{desired.adjective} and {undesired.adjective}"

    responses_dir = Path(args.responses_dir) if args.responses_dir else RESULTS_DIR / cfg.experiment_id / "responses"
    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR / cfg.experiment_id / "scored"
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = RESULTS_DIR / cfg.experiment_id / "metrics.csv"

    response_files = sorted(responses_dir.glob("*.jsonl"))
    if not response_files:
        log.error("No response files found in %s", responses_dir)
        sys.exit(1)

    log.info("=" * 60)
    log.info("Phase 4b — Scoring Evaluation Responses")
    log.info("  Condition      : %s", cfg.condition_name)
    log.info("  Experiment     : %s", cfg.experiment_id)
    log.info("  Desired trait  : %s (%s)", desired.noun, desired.adjective)
    log.info("  Undesired trait: %s (%s)", undesired.noun, undesired.adjective)
    log.info("  Coherence      : %s", "enabled" if do_coherence else "disabled")
    log.info("  Response files : %d", len(response_files))
    log.info("  Judge model    : %s", cfg.eval.judge_model)
    log.info("  Output         : %s", output_dir)
    log.info("=" * 60)

    all_scored: list[dict] = []

    for resp_file in response_files:
        scored_path = output_dir / resp_file.name
        records = read_jsonl(resp_file)

        if not records:
            log.warning("Empty file: %s — skipping.", resp_file)
            continue

        # Resume: load existing scored records and skip already-done ones
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
            log.info("[%s] All %d records already scored — skipping.", resp_file.name, len(records))
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

        # Optional coherence scoring
        coherence_scores: list[float | None] | None = None
        if do_coherence:
            coherence_scores = score_coherence(
                todo,
                trait_context=trait_context,
                api_key=args.api_key,
                max_workers=cfg.eval.judge_max_workers,
            )

        # Merge scores into records
        for i, rec in enumerate(todo):
            rec["desired_score"] = desired_scores[i]
            rec["undesired_score"] = undesired_scores[i]
            if coherence_scores is not None:
                rec["coherence_score"] = coherence_scores[i]

        # Combine with existing and write
        all_for_file = existing_records + todo
        write_jsonl(all_for_file, scored_path)
        log.info("[%s] Wrote %d scored records → %s",
                 resp_file.name, len(all_for_file), scored_path)

        all_scored.extend(all_for_file)

    # Compute and save aggregate metrics
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
    """Unique key for a single scored record (used for resume logic)."""
    return f"{rec.get('model_id', '')}|{rec.get('probe_name', '')}|{rec.get('dataset', '')}|{rec.get('query_idx', '')}"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score eval responses with logprobs judge.")
    p.add_argument("--config", required=True, help="Path to YAML experiment config.")
    p.add_argument("--api-key", default=None,
                   help="OpenAI API key (default: OPENAI_API_KEY env var).")
    p.add_argument("--no-coherence", action="store_true",
                   help="Disable coherence scoring even if config enables it.")
    p.add_argument("--responses-dir", default=None,
                   help="Directory with response JSONL files (default: results/{id}/responses/).")
    p.add_argument("--output-dir", default=None,
                   help="Output directory for scored JSONL files (default: results/{id}/scored/).")
    return p.parse_args()


if __name__ == "__main__":
    main()
