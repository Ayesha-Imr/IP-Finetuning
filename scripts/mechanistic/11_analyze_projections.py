"""
11 — Analyze response projections.

Loads .pt files from script 10, computes cosine similarity, causal similarity,
and causal projection between first-response-token activations and the trait
direction, then generates plots and CSV.

Usage:
    python scripts/mechanistic/11_analyze_projections.py \\
        configs/mechanistic/response_projection.yaml
"""

import argparse
import csv
import logging
from pathlib import Path

import torch

from ip_finetuning.mechanistic.config import MechanisticConfig
from ip_finetuning.mechanistic.extraction import load_activations
from ip_finetuning.mechanistic.projection_analysis import (
    compute_projection_matrix,
    plot_layer_sweep,
    plot_layer_sweep_delta,
    plot_metric_comparison,
    plot_multi_layer_projection,
    plot_projection_heatmap,
    plot_projection_profile,
    projection_summary_table,
)
from ip_finetuning.mechanistic.prompt_tiers import load_prompt_tiers

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Analyze response projections")
    parser.add_argument("--config", required=True, help="Path to mechanistic config YAML")
    args = parser.parse_args()

    cfg = MechanisticConfig.from_yaml(args.config)
    project_root = Path(__file__).resolve().parent.parent.parent
    data_root = project_root / cfg.results_dir / cfg.experiment_name
    plots_dir = data_root / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    tiers = load_prompt_tiers(project_root / cfg.prompt_tiers_file)
    tier_order = [t.name for t in tiers]
    tier_display = {t.name: t.display_name for t in tiers}
    layers = cfg.extraction.layers
    metrics = cfg.extraction.metrics

    trait_pair_label = (
        f"undesired: {cfg.trait_noun}  |  desired: {cfg.desired_trait}"
        if cfg.desired_trait else ""
    )

    all_model_names = ["base"] + [m.name for m in cfg.models]

    # Load Gram matrix
    gram_data = load_activations(data_root / "gram_matrix.pt")
    G = gram_data["gram_matrix"]

    # Load trait directions
    base_td = load_activations(data_root / "base" / "trait_direction.pt")
    base_direction = base_td["directions"]

    own_directions: dict[str, dict[int, torch.Tensor]] = {"base": base_direction}
    if cfg.trait_direction_source in ("own", "both"):
        for m in cfg.models:
            td = load_activations(data_root / m.name / "trait_direction.pt")
            own_directions[m.name] = td["directions"]

    # Load response activations
    response_acts: dict[str, dict[str, dict[int, list[torch.Tensor]]]] = {}
    for model_name in all_model_names:
        response_acts[model_name] = load_activations(
            data_root / model_name / "response_activations.pt"
        )

    # Compute projection matrices
    log.info("Computing projection matrices...")

    # Always compute with base direction
    proj_base: dict[str, dict[str, dict[int, dict[str, float]]]] = {}
    for model_name in all_model_names:
        proj_base[model_name] = compute_projection_matrix(
            response_acts[model_name], base_direction, layers, metrics, G,
        )

    # Optionally compute with own direction
    proj_own = None
    if cfg.trait_direction_source in ("own", "both"):
        proj_own = {}
        for model_name in all_model_names:
            direction = own_directions.get(model_name, base_direction)
            proj_own[model_name] = compute_projection_matrix(
                response_acts[model_name], direction, layers, metrics, G,
            )

    # --- Plots ---
    log.info("Generating plots...")

    # Determine key layers for detailed plots
    final_layer = layers[-1]
    mid_layer = layers[len(layers) // 2]

    # 1. Per-metric projection profiles at key layers (base direction)
    for metric in metrics:
        for layer in [mid_layer, final_layer]:
            plot_projection_profile(
                proj_base, tier_order, tier_display, layer, metric,
                title=f"Response Projection (base direction) — L{layer} ({metric})",
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"profile_base_{metric}_L{layer}.png",
            )

    # 2. Multi-layer grid per metric (base direction)
    for metric in metrics:
        plot_multi_layer_projection(
            proj_base, tier_order, tier_display, layers, metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"multi_layer_base_{metric}.png",
        )

    # 3. Layer sweep at explicit and neutral tiers (base direction)
    for metric in metrics:
        for tier in [tier_order[0], tier_order[-1]]:
            display = tier_display[tier]
            plot_layer_sweep(
                proj_base, layers, tier, display, metric,
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"layer_sweep_{tier}_{metric}.png",
            )

    # 4. Layer sweep delta (explicit - neutral) per metric
    for metric in metrics:
        plot_layer_sweep_delta(
            proj_base, layers, tier_order, metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"layer_sweep_delta_{metric}.png",
        )

    # 5. Metric comparison at final layer
    if len(metrics) > 1:
        plot_metric_comparison(
            proj_base, tier_order, tier_display, final_layer, metrics,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"metric_comparison_L{final_layer}.png",
        )

    # 6. Per-model heatmaps (base direction, primary metric)
    primary_metric = "causal_projection" if "causal_projection" in metrics else metrics[0]
    for model_name in all_model_names:
        plot_projection_heatmap(
            proj_base[model_name], tier_order, tier_display, layers,
            model_name, primary_metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"heatmap_{model_name}_{primary_metric}.png",
        )

    # 7. Own-direction plots (if applicable)
    if proj_own is not None:
        for metric in metrics:
            plot_projection_profile(
                proj_own, tier_order, tier_display, final_layer, metric,
                title=f"Response Projection (own direction) — L{final_layer} ({metric})",
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"profile_own_{metric}_L{final_layer}.png",
            )

    # --- CSV export ---
    log.info("Exporting CSV...")

    fieldnames = ["model", "tier", "layer"] + metrics
    rows = projection_summary_table(proj_base, tier_order, layers, metrics)
    csv_path = data_root / "projections_base.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    log.info("  Saved: %s", csv_path)

    if proj_own is not None:
        rows = projection_summary_table(proj_own, tier_order, layers, metrics)
        csv_path = data_root / "projections_own.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        log.info("  Saved: %s", csv_path)

    log.info("Done. Plots in: %s", plots_dir)


if __name__ == "__main__":
    main()
