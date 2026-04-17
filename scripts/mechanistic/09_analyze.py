"""
09 — Analyze conditionalization profiles.

Loads .pt files from script 08, computes cosine similarities between
prompt-tier activations and trait directions, generates plots and CSV.

Usage:
    python scripts/mechanistic/09_analyze.py \\
        configs/mechanistic/conditionalization_narrowing.yaml
"""

import argparse
import csv
import logging
from pathlib import Path

import torch

from ip_finetuning.mechanistic.analysis import (
    compute_alignment_matrix,
    plot_conditionalization_heatmap,
    plot_conditionalization_profile,
    plot_direction_comparison,
    plot_multi_layer_profiles,
    summary_table,
)
from ip_finetuning.mechanistic.config import MechanisticConfig
from ip_finetuning.mechanistic.extraction import load_activations
from ip_finetuning.mechanistic.prompt_tiers import load_prompt_tiers

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Analyze conditionalization profiles")
    parser.add_argument("config", help="Path to mechanistic config YAML")
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

    all_model_names = ["base"] + [m.name for m in cfg.models]

    # Load trait directions and prompt gradient activations 

    # Per-model directions
    own_directions: dict[str, dict[int, torch.Tensor]] = {}
    prompt_acts: dict[str, dict[str, dict[int, list[torch.Tensor]]]] = {}

    for model_name in all_model_names:
        model_dir = data_root / model_name
        td = load_activations(model_dir / "trait_direction.pt")
        own_directions[model_name] = td["directions"]
        prompt_acts[model_name] = load_activations(model_dir / "prompt_gradient.pt")

    base_direction = own_directions["base"]

    # Compute alignment matrices

    # Alignment with own direction
    alignment_own: dict[str, dict[str, dict[int, float]]] = {}
    for model_name in all_model_names:
        alignment_own[model_name] = compute_alignment_matrix(
            prompt_acts[model_name], own_directions[model_name], layers,
        )

    # Alignment with base direction
    alignment_base: dict[str, dict[str, dict[int, float]]] = {}
    for model_name in all_model_names:
        alignment_base[model_name] = compute_alignment_matrix(
            prompt_acts[model_name], base_direction, layers,
        )

    # Plots

    log.info("Generating plots...")

    # 1. Per-layer conditionalization profiles (own direction)
    for layer in layers:
        plot_conditionalization_profile(
            alignment_own, tier_order, tier_display, layer,
            title=f"Conditionalization Profile (own direction) — Layer {layer}",
            save_path=plots_dir / f"profile_own_L{layer}.png",
        )

    # 2. Per-layer conditionalization profiles (base direction)
    for layer in layers:
        plot_conditionalization_profile(
            alignment_base, tier_order, tier_display, layer,
            title=f"Conditionalization Profile (base direction) — Layer {layer}",
            save_path=plots_dir / f"profile_base_L{layer}.png",
        )

    # 3. Multi-layer grid (own direction)
    plot_multi_layer_profiles(
        alignment_own, tier_order, tier_display, layers,
        save_path=plots_dir / "multi_layer_own.png",
    )

    # 4. Multi-layer grid (base direction)
    plot_multi_layer_profiles(
        alignment_base, tier_order, tier_display, layers,
        save_path=plots_dir / "multi_layer_base.png",
    )

    # 5. Direction comparison (own vs base) at key layer
    for layer in [16, 20]:
        plot_direction_comparison(
            alignment_own, alignment_base, tier_order, tier_display, layer,
            save_path=plots_dir / f"direction_comparison_L{layer}.png",
        )

    # 6. Per-model heatmaps (own direction)
    for model_name in all_model_names:
        plot_conditionalization_heatmap(
            alignment_own[model_name], tier_order, tier_display, layers, model_name,
            save_path=plots_dir / f"heatmap_{model_name}.png",
        )

    # CSV export

    log.info("Exporting summary CSV...")

    for direction_type, alignment_data in [("own", alignment_own), ("base", alignment_base)]:
        rows = summary_table(alignment_data, tier_order, layers)
        csv_path = data_root / f"alignment_{direction_type}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["model", "tier", "layer", "cosine_sim"])
            writer.writeheader()
            writer.writerows(rows)
        log.info("  Saved: %s", csv_path)

    log.info("Done. Plots in: %s", plots_dir)


if __name__ == "__main__":
    main()
