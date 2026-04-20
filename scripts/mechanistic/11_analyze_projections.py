"""
11 — Analyze response projections.

Loads .pt files from script 10, computes cosine similarity, causal similarity,
and causal projection between response-token activations and the trait direction,
then generates plots and CSV.

Single-position mode (probe_positions=[0])

Multi-position mode (probe_positions=[0..N])
    

Usage:
    python scripts/mechanistic/11_analyze_projections.py \\
        --config configs/mechanistic/response_projection_playful_french.yaml
"""

import argparse
import csv
import logging
from pathlib import Path

import pandas as pd
import torch

from ip_finetuning.mechanistic.config import MechanisticConfig
from ip_finetuning.mechanistic.extraction import load_activations
from ip_finetuning.mechanistic.projection_analysis import (
    compute_projection_matrix,
    compute_projection_matrix_multipos,
    filter_by_token_category,
    plot_layer_sweep,
    plot_layer_sweep_delta,
    plot_metric_comparison,
    plot_multi_layer_projection,
    plot_position_convergence,
    plot_position_layer_delta,
    plot_projection_heatmap,
    plot_projection_profile,
    plot_token_match_comparison,
    projection_summary_table,
    _is_multipos_acts,
    _is_multipos_direction,
)
from ip_finetuning.mechanistic.prompt_tiers import load_prompt_tiers

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)


def _load_directions(data_root: Path, cfg, all_model_names: list[str]) -> tuple[dict, dict]:
    """Load trait directions. Returns (base_direction, own_directions).

    base_direction : {layer: tensor}            (single-pos) OR
                     {pos: {layer: tensor}}      (multi-pos)
    own_directions : {model_name: same as above}
    """
    base_td = load_activations(data_root / "base" / "trait_direction.pt")
    base_direction = base_td["directions"]

    own_dirs: dict = {"base": base_direction}
    if cfg.trait_direction_source in ("own", "both"):
        for m in cfg.models:
            td = load_activations(data_root / m.name / "trait_direction.pt")
            own_dirs[m.name] = td["directions"]

    return base_direction, own_dirs


def _run_singlepos_analysis(
    cfg, data_root: Path, plots_dir: Path,
    response_acts, base_direction, G,
    tier_order, tier_display, layers, metrics, trait_pair_label,
    all_model_names,
) -> None:
    """Experiment 2: single-position projection analysis + plots."""

    proj_base: dict = {}
    for model_name in all_model_names:
        proj_base[model_name] = compute_projection_matrix(
            response_acts[model_name], base_direction, layers, metrics, G,
        )

    final_layer = layers[-1]
    mid_layer = layers[len(layers) // 2]

    # 1. Projection profiles at key layers
    for metric in metrics:
        for layer in [mid_layer, final_layer]:
            plot_projection_profile(
                proj_base, tier_order, tier_display, layer, metric,
                title=f"Response Projection (base direction) — L{layer} ({metric})",
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"profile_base_{metric}_L{layer}.png",
            )

    # 2. Multi-layer grid
    for metric in metrics:
        plot_multi_layer_projection(
            proj_base, tier_order, tier_display, layers, metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"multi_layer_base_{metric}.png",
        )

    # 3. Layer sweep at explicit / neutral tiers
    for metric in metrics:
        for tier in [tier_order[0], tier_order[-1]]:
            plot_layer_sweep(
                proj_base, layers, tier, tier_display[tier], metric,
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"layer_sweep_{tier}_{metric}.png",
            )

    # 4. ★ HIGH SIGNAL: Layer sweep delta (explicit − neutral)
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

    # 6. Per-model heatmaps
    primary_metric = "causal_projection" if "causal_projection" in metrics else metrics[0]
    for model_name in all_model_names:
        plot_projection_heatmap(
            proj_base[model_name], tier_order, tier_display, layers,
            model_name, primary_metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"heatmap_{model_name}_{primary_metric}.png",
        )

    # CSV export
    fieldnames = ["model", "tier", "layer"] + metrics
    rows = projection_summary_table(proj_base, tier_order, layers, metrics)
    csv_path = data_root / "projections_base.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Saved: %s", csv_path)


def _run_multipos_analysis(
    cfg, data_root: Path, plots_dir: Path,
    response_acts_raw, base_direction_raw, G,
    tier_order, tier_display, layers, metrics, trait_pair_label,
    all_model_names,
) -> None:
    """Experiment 3: multi-position disentanglement analysis + 3 high-signal plots."""
    positions = cfg.extraction.probe_positions

    # Normalise response_acts to {model: {tier: {pos: {layer: [tensors]}}}}
    def _to_multipos(acts_raw):
        """Wrap single-position {tier: {layer: [t]}} into {tier: {0: {layer: [t]}}}."""
        first_tier = next(iter(acts_raw.values()))
        if _is_multipos_acts(acts_raw):
            return acts_raw
        return {tier: {0: lacts} for tier, lacts in acts_raw.items()}

    response_acts: dict[str, dict] = {
        m: _to_multipos(response_acts_raw[m]) for m in all_model_names
    }

    # Reorganise as {pos: {model: {tier: {layer: [tensors]}}}}  for compute
    def _build_acts_by_pos(response_acts_by_model, positions):
        acts_by_pos = {}
        for pos in positions:
            acts_by_pos[pos] = {
                model: {tier: data[pos] for tier, data in tier_data.items()}
                for model, tier_data in response_acts_by_model.items()
            }
        return acts_by_pos

    acts_by_pos = _build_acts_by_pos(response_acts, positions)

    # Normalise directions to {model: {pos: {layer: tensor}}}
    def _to_multipos_dir(dirs_raw):
        if _is_multipos_direction(dirs_raw):
            return dirs_raw  # already {pos: {layer: tensor}}
        return {0: dirs_raw}  # wrap single-pos

    directions_by_model: dict[str, dict[int, dict]] = {
        m: _to_multipos_dir(base_direction_raw)  # use base direction for all models
        for m in all_model_names
    }

    # Compute projections per model per position
    # proj_by_model: {model: {pos: {tier: {layer: {metric: float}}}}}
    proj_by_model: dict[str, dict] = {}
    for model_name in all_model_names:
        acts_for_model = {
            pos: {
                tier: response_acts[model_name][tier][pos]
                for tier in tier_order
                if tier in response_acts[model_name]
            }
            for pos in positions
        }
        proj_by_model[model_name] = compute_projection_matrix_multipos(
            acts_for_model,
            directions_by_model[model_name],
            layers, metrics, G,
        )

    # Reformat for plots: {model: {pos: {tier: {layer: {metric: float}}}}}
    proj_by_pos_by_model = proj_by_model

    # ── Plot 1: Position-resolved layer sweep delta ────────────────────────────
    for metric in metrics:
        plot_position_layer_delta(
            proj_by_pos_by_model, layers, tier_order, metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"position_layer_delta_{metric}.png",
        )

    # ── Plot 2: Token-matched comparison (if configured) ──────────────────────
    if cfg.token_match_category:
        audit_dfs: dict[str, pd.DataFrame] = {}
        for model_name in all_model_names:
            audit_path = data_root / model_name / "probe_tokens_audit.csv"
            if audit_path.exists():
                audit_dfs[model_name] = pd.read_csv(audit_path)

        # Build matched acts for pos=0 only (token matching is on first token)
        matched_response_acts: dict[str, dict] = {}
        for model_name in all_model_names:
            if model_name not in audit_dfs:
                log.warning("No audit CSV for %s — skipping token matching", model_name)
                continue
            raw_acts_pos0 = {
                tier: response_acts[model_name][tier].get(0, {})
                for tier in tier_order
            }
            # Build experiment key matching TRAIT_TOKEN_SETS keys (e.g. "french_playfulness")
            exp_key = f"{cfg.trait_adjective.lower()}_{cfg.desired_trait.lower()}"
            filtered = filter_by_token_category(
                raw_acts_pos0, audit_dfs[model_name],
                cfg.token_match_category,
                exp_key,
            )
            matched_response_acts[model_name] = filtered

        # Compute projections on matched subset (at pos=0 only)
        proj_matched: dict[str, dict] = {}
        for model_name in matched_response_acts:
            dirs_pos0 = directions_by_model[model_name].get(0, {})
            proj_matched[model_name] = compute_projection_matrix(
                matched_response_acts[model_name], dirs_pos0, layers, metrics, G,
            )

        # Unmatched = pos=0 projections from the full set
        proj_unmatched: dict[str, dict] = {}
        for model_name in all_model_names:
            dirs_pos0 = directions_by_model[model_name].get(0, {})
            proj_unmatched[model_name] = compute_projection_matrix(
                {tier: response_acts[model_name][tier].get(0, {}) for tier in tier_order},
                dirs_pos0, layers, metrics, G,
            )

        for metric in metrics:
            plot_token_match_comparison(
                proj_unmatched, proj_matched, layers, tier_order, metric,
                match_label=cfg.token_match_category,
                trait_pair_label=trait_pair_label,
                save_path=plots_dir / f"token_match_comparison_{metric}.png",
            )

        # Save matched projections CSV
        rows_matched = projection_summary_table(proj_matched, tier_order, layers, metrics)
        csv_path = data_root / "projections_matched.csv"
        fieldnames = ["model", "tier", "layer"] + metrics
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_matched)
        log.info("Saved: %s", csv_path)

    # ── Plot 3: Position convergence at mid-layer ──────────────────────────────
    pivot_layer = layers[len(layers) // 2]  # e.g. L16 for [0,8,16,27]
    for metric in metrics:
        plot_position_convergence(
            proj_by_pos_by_model, positions, pivot_layer, tier_order, metric,
            trait_pair_label=trait_pair_label,
            save_path=plots_dir / f"position_convergence_L{pivot_layer}_{metric}.png",
        )

    # CSV: full multi-position projections (long format)
    rows: list[dict] = []
    fieldnames_mp = ["model", "position", "tier", "layer"] + metrics
    for model_name, by_pos in proj_by_pos_by_model.items():
        for pos, tier_data in by_pos.items():
            for tier in tier_order:
                for layer in layers:
                    row = {"model": model_name, "position": pos, "tier": tier, "layer": layer}
                    for metric in metrics:
                        row[metric] = tier_data.get(tier, {}).get(layer, {}).get(metric, "")
                    rows.append(row)
    csv_path = data_root / "projections_multipos.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_mp)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Saved: %s", csv_path)


def main():
    parser = argparse.ArgumentParser(description="Analyze response projections")
    parser.add_argument("--config", required=True, help="Path to mechanistic config YAML")
    args = parser.parse_args()

    cfg = MechanisticConfig.from_yaml(args.config)
    project_root = Path(__file__).resolve().parent.parent.parent
    data_root = project_root / cfg.results_dir / cfg.experiment_name

    multipos = cfg.extraction.probe_positions != [0]
    plots_dir = data_root / ("plots_multipos" if multipos else "plots")
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
    G = load_activations(data_root / "gram_matrix.pt")["gram_matrix"]

    # Load trait directions
    base_direction_raw, _ = _load_directions(data_root, cfg, all_model_names)

    # Load response activations
    response_acts_raw: dict[str, dict] = {
        model_name: load_activations(data_root / model_name / "response_activations.pt")
        for model_name in all_model_names
    }

    log.info("Computing projections (multipos=%s)...", multipos)

    if multipos:
        _run_multipos_analysis(
            cfg, data_root, plots_dir,
            response_acts_raw, base_direction_raw, G,
            tier_order, tier_display, layers, metrics, trait_pair_label,
            all_model_names,
        )
    else:
        _run_singlepos_analysis(
            cfg, data_root, plots_dir,
            response_acts_raw, base_direction_raw, G,
            tier_order, tier_display, layers, metrics, trait_pair_label,
            all_model_names,
        )

    log.info("Done. Plots in: %s", plots_dir)


if __name__ == "__main__":
    main()
