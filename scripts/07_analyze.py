"""
Script 07: Analyse and visualise scored evaluation results.

Reads:
  results/{experiment_id}/scored/   (output of script 06)

Produces (in results/{experiment_id}/figures/):
  heatmap_{dataset}.png             — Probe × model heatmap (desired + undesired)
  scatter_{dataset}.png             — Desired vs suppression scatter grid
  summary_{dataset}.csv / .md       — Summary table

Usage
-----
    # Generate all analyses for one experiment:
    python scripts/07_analyze.py --config configs/examples/rrdn4_b50.yaml

    # Filter to one dataset:
    python scripts/07_analyze.py --config configs/examples/rrdn4_b50.yaml \\
        --dataset ultrachat

    # Skip table generation:
    python scripts/07_analyze.py --config configs/examples/rrdn4_b50.yaml --no-tables

    # Custom output dir:
    python scripts/07_analyze.py --config configs/examples/rrdn4_b50.yaml \\
        --output-dir results/my_analysis

    # Analyse multiple experiments together (compare conditions):
    python scripts/07_analyze.py \\
        --config configs/examples/rrdn4_b50.yaml \\
        --extra-ids C2_abc12345 C4_def67890
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.traits import resolve_trait

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path("results")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)

    desired = resolve_trait(cfg.trait_pair.desired_trait)
    undesired = resolve_trait(cfg.trait_pair.undesired_trait)

    # Collect experiment IDs to load
    experiment_ids = [cfg.experiment_id]
    if args.extra_ids:
        experiment_ids.extend(args.extra_ids)

    results_dir = Path(args.results_dir) if args.results_dir else RESULTS_DIR
    output_dir = Path(args.output_dir) if args.output_dir else results_dir / cfg.experiment_id / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name = cfg.training.base_model_id.split("/")[-1]

    log.info("=" * 60)
    log.info("Phase 5 — Analysis & Visualization")
    log.info("  Condition      : %s", cfg.condition_name)
    log.info("  Experiment     : %s", cfg.experiment_id)
    log.info("  Desired trait  : %s (%s)", desired.noun, desired.adjective)
    log.info("  Undesired trait: %s (%s)", undesired.noun, undesired.adjective)
    log.info("  Experiments    : %s", experiment_ids)
    log.info("  Output         : %s", output_dir)
    log.info("=" * 60)

    # --- Load scored data ---
    from ip_finetuning.analysis.load import load_experiments
    df = load_experiments(experiment_ids, results_dir=results_dir)
    log.info("Loaded %d scored records across %d experiment(s).", len(df), len(experiment_ids))

    # Determine which datasets are present
    datasets = [args.dataset] if args.dataset else sorted(df["dataset"].unique())

    # Get probe ordering from config
    probe_order = [p.name for p in cfg.eval.probes] if cfg.eval.probes else None

    for ds in datasets:
        log.info("--- Dataset: %s ---", ds)
        ds_suffix = f"_{ds}" if len(datasets) > 1 else ""

        # --- Heatmap ---
        if not args.no_heatmap:
            from ip_finetuning.analysis.heatmaps import plot_heatmap_pair
            fig = plot_heatmap_pair(
                df,
                desired_adj=desired.adjective,
                undesired_adj=undesired.adjective,
                model_name=model_name,
                dataset=ds,
                probe_order=probe_order,
                save_path=output_dir / f"heatmap{ds_suffix}.png",
            )
            import matplotlib.pyplot as plt
            plt.close(fig)
            log.info("  Heatmap saved.")

        # --- Scatter ---
        if not args.no_scatter:
            from ip_finetuning.analysis.scatter import plot_tradeoff_scatter
            fig = plot_tradeoff_scatter(
                df,
                desired_adj=desired.adjective,
                undesired_adj=undesired.adjective,
                model_name=model_name,
                dataset=ds,
                save_path=output_dir / f"scatter{ds_suffix}.png",
            )
            import matplotlib.pyplot as plt
            plt.close(fig)
            log.info("  Scatter saved.")

        # --- Table ---
        if not args.no_tables:
            from ip_finetuning.analysis.tables import summary_table, save_summary
            table = summary_table(
                df,
                desired_adj=desired.adjective,
                undesired_adj=undesired.adjective,
                dataset=ds,
            )
            save_summary(table, output_dir / f"summary{ds_suffix}")
            log.info("  Summary table saved.")

    log.info("All analyses written to %s", output_dir)
    log.info("Done.")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analyse and visualise scored evaluation results.",
    )
    p.add_argument("--config", required=True, help="Path to YAML experiment config.")
    p.add_argument("--dataset", default=None,
                   help="Filter to one dataset (e.g. 'ultrachat'). Default: all.")
    p.add_argument("--extra-ids", nargs="*", default=None,
                   help="Extra experiment IDs to include (for cross-condition comparison).")
    p.add_argument("--output-dir", default=None,
                   help="Custom output directory for figures/tables.")
    p.add_argument("--results-dir", default=None,
                   help="Root results directory (default: results/).")
    p.add_argument("--no-heatmap", action="store_true", help="Skip heatmap generation.")
    p.add_argument("--no-scatter", action="store_true", help="Skip scatter plot generation.")
    p.add_argument("--no-tables", action="store_true", help="Skip table generation.")
    return p.parse_args()


if __name__ == "__main__":
    main()
