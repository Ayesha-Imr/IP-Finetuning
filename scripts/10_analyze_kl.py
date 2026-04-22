"""
Script 10-KL: Generate lambda sensitivity plots for KL experiments.

Reads metrics.csv from multiple KL experiment results and produces
a lambda sensitivity figure showing key probe scores vs lambda.

Usage
-----
    python scripts/10_analyze_kl.py \\
        --experiment-ids KL-C2-french_lam0p1_abc KL-C2-french_lam0p5_abc ... \\
        --lambdas 0.1 0.5 1.0 5.0 \\
        --trait-pair "French / Playful" \\
        --ip-strategy "Fixed IP" \\
        --output results/kl_analysis/lambda_sensitivity_french_fixed.png
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path("results")


def main() -> None:
    args = _parse_args()

    from ip_finetuning.analysis.kl_plots import plot_lambda_sensitivity

    results = []
    for exp_id, lam in zip(args.experiment_ids, args.lambdas):
        metrics_path = RESULTS_DIR / exp_id / "metrics.csv"
        if not metrics_path.exists():
            log.warning("metrics.csv not found for %s — skipping.", exp_id)
            continue
        results.append({
            "lambda_val": lam,
            "metrics_path": metrics_path,
        })

    if not results:
        log.error("No valid experiment results found.")
        sys.exit(1)

    output_path = Path(args.output)
    plot_lambda_sensitivity(
        results,
        trait_pair_label=args.trait_pair,
        ip_strategy=args.ip_strategy,
        output_path=output_path,
        dataset=args.dataset,
    )
    log.info("Done.")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lambda sensitivity analysis for KL experiments.")
    p.add_argument("--experiment-ids", nargs="+", required=True, help="Experiment IDs (in lambda order).")
    p.add_argument("--lambdas", nargs="+", type=float, required=True, help="Lambda values (matching experiment IDs).")
    p.add_argument("--trait-pair", required=True, help="Label for trait pair, e.g. 'French / Playful'.")
    p.add_argument("--ip-strategy", required=True, help="Label for IP strategy, e.g. 'Fixed IP'.")
    p.add_argument("--output", required=True, help="Output path for the figure.")
    p.add_argument("--dataset", default="ultrachat", help="Dataset to filter on.")
    return p.parse_args()


if __name__ == "__main__":
    main()
