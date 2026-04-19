"""
Analysis and visualization for response projection experiments.

Computes cosine similarity, causal similarity, and causal projection between
first-response-token activations and trait directions, then produces plots.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

from ip_finetuning.mechanistic.causal_metrics import (
    causal_projection,
    causal_similarity,
    cosine_similarity,
)

log = logging.getLogger(__name__)


# Reuse style constants from existing analysis module
from ip_finetuning.mechanistic.analysis import (
    BG_CARD,
    BG_FIGURE,
    FIGURE_DPI,
    FONT_SIZES,
    MODEL_COLORS,
    _clean_ax,
    _set_theme,
)

METRIC_LABELS = {
    "cosine": "Cosine similarity",
    "causal_similarity": "Causal similarity",
    "causal_projection": "Causal projection",
}


# Multi-metric alignment computation

def _compute_single(a: torch.Tensor, b: torch.Tensor, metric: str, G: torch.Tensor | None) -> float:
    if metric == "cosine":
        return cosine_similarity(a, b)
    elif metric == "causal_similarity":
        return causal_similarity(a, b, G)
    elif metric == "causal_projection":
        return causal_projection(a, b, G)
    raise ValueError(f"Unknown metric: {metric}")


def compute_projection_matrix(
    response_acts: dict[str, dict[int, list[torch.Tensor]]],
    trait_direction: dict[int, torch.Tensor],
    layers: list[int],
    metrics: list[str],
    gram_matrix: torch.Tensor | None = None,
) -> dict[str, dict[int, dict[str, float]]]:
    """Compute mean metric values per tier per layer.

    Returns: {tier_name: {layer: {metric: mean_value}}}
    """
    result = {}
    for tier_name, layer_acts in response_acts.items():
        result[tier_name] = {}
        for l in layers:
            if l not in trait_direction:
                continue
            direction = trait_direction[l]
            result[tier_name][l] = {}
            for metric in metrics:
                vals = [_compute_single(a, direction, metric, gram_matrix) for a in layer_acts[l]]
                result[tier_name][l][metric] = float(np.mean(vals))
    return result


# --- Visualization ---

def plot_projection_profile(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layer: int,
    metric: str,
    *,
    title: str = "",
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Line plot: metric vs prompt tier for each model at one layer."""
    import matplotlib.pyplot as plt

    _set_theme()
    fig, ax = plt.subplots(figsize=(8, 4.5))

    x = np.arange(len(tier_order))
    for i, (model_name, tier_data) in enumerate(data_by_model.items()):
        y = [tier_data[t][layer][metric] for t in tier_order]
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        ax.plot(x, y, marker="o", markersize=6, linewidth=2, label=model_name,
                color=color, alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels([tier_display[t] for t in tier_order], rotation=25, ha="right")
    ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=FONT_SIZES["axis_label"])
    ax.set_xlabel("Prompt tier", fontsize=FONT_SIZES["axis_label"])
    full_title = title or f"Response Projection — Layer {layer} ({metric})"
    if trait_pair_label:
        full_title += f"\n{trait_pair_label}"
    ax.set_title(full_title, fontsize=FONT_SIZES["title"], pad=12)
    ax.legend(loc="best", fontsize=FONT_SIZES["legend"])
    _clean_ax(ax)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def plot_multi_layer_projection(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layers: list[int],
    metric: str,
    *,
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Grid of projection profiles: one subplot per layer."""
    import matplotlib.pyplot as plt

    _set_theme()
    n = len(layers)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.5 * cols, 3.5 * rows), squeeze=False)

    x = np.arange(len(tier_order))
    model_names = list(data_by_model.keys())

    for idx, layer in enumerate(layers):
        r, c = divmod(idx, cols)
        ax = axes[r][c]
        for i, model_name in enumerate(model_names):
            y = [data_by_model[model_name][t][layer][metric] for t in tier_order]
            color = MODEL_COLORS[i % len(MODEL_COLORS)]
            ax.plot(x, y, marker="o", markersize=4, linewidth=1.5,
                    label=model_name, color=color, alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels([tier_display[t] for t in tier_order],
                           rotation=30, ha="right", fontsize=FONT_SIZES["tick"] - 1)
        ax.set_ylabel(METRIC_LABELS.get(metric, metric)[:10] + ".",
                      fontsize=FONT_SIZES["axis_label"] - 1)
        ax.set_title(f"L{layer}", fontsize=FONT_SIZES["title"] - 1, pad=6)
        _clean_ax(ax)
        ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    for idx in range(n, rows * cols):
        r, c = divmod(idx, cols)
        axes[r][c].set_visible(False)

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(len(model_names), 5),
               fontsize=FONT_SIZES["legend"], bbox_to_anchor=(0.5, -0.02))
    suptitle_str = f"Response Projection Across Layers — {METRIC_LABELS.get(metric, metric)}"
    if trait_pair_label:
        suptitle_str += f"\n{trait_pair_label}"
    fig.suptitle(suptitle_str, fontsize=FONT_SIZES["suptitle"], fontweight="bold", y=1.01)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def plot_projection_heatmap(
    data: dict[str, dict[int, dict[str, float]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layers: list[int],
    model_name: str,
    metric: str,
    *,
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Heatmap: rows=tiers, cols=layers for one model and metric."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    _set_theme()
    n_tiers = len(tier_order)
    n_layers = len(layers)
    fig, ax = plt.subplots(figsize=(2 + n_layers * 0.85, 1.5 + n_tiers * 0.7))

    matrix = np.zeros((n_tiers, n_layers))
    for i, tier in enumerate(tier_order):
        for j, layer in enumerate(layers):
            matrix[i, j] = data[tier][layer][metric]

    vmin, vmax = matrix.min() - 0.02, matrix.max() + 0.02
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.RdYlBu_r
    im = ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

    for i in range(n_tiers):
        for j in range(n_layers):
            val = matrix[i, j]
            brightness = cmap(norm(val))[:3]
            text_color = "#FFFFFF" if sum(brightness) < 1.5 else "#2B2B2B"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=FONT_SIZES["annotation"] - 0.5, color=text_color, fontweight="bold")

    ax.set_xticks(range(n_layers))
    ax.set_xticklabels([f"L{l}" for l in layers], fontsize=FONT_SIZES["tick"] - 1)
    ax.set_yticks(range(n_tiers))
    ax.set_yticklabels([tier_display[t] for t in tier_order])
    ax.set_xlabel("Layer", fontsize=FONT_SIZES["axis_label"])
    heatmap_title = f"{model_name} — {METRIC_LABELS.get(metric, metric)}"
    if trait_pair_label:
        heatmap_title += f"\n{trait_pair_label}"
    ax.set_title(heatmap_title, fontsize=FONT_SIZES["title"], pad=12)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.04)
    cbar.set_label(METRIC_LABELS.get(metric, metric), fontsize=FONT_SIZES["annotation"])
    cbar.ax.tick_params(labelsize=FONT_SIZES["tick"] - 1)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def plot_layer_sweep(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    layers: list[int],
    tier_name: str,
    tier_display_name: str,
    metric: str,
    *,
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Line plot: metric vs layer for each model at a fixed tier.

    Shows WHERE in the network models diverge — the routing signal.
    """
    import matplotlib.pyplot as plt

    _set_theme()
    fig, ax = plt.subplots(figsize=(9, 4.5))

    for i, (model_name, tier_data) in enumerate(data_by_model.items()):
        y = [tier_data[tier_name][l][metric] for l in layers]
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        ax.plot(layers, y, marker="o", markersize=5, linewidth=2, label=model_name,
                color=color, alpha=0.9)

    ax.set_xlabel("Layer", fontsize=FONT_SIZES["axis_label"])
    ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=FONT_SIZES["axis_label"])
    sweep_title = f"Layer Sweep — {tier_display_name} tier ({METRIC_LABELS.get(metric, metric)})"
    if trait_pair_label:
        sweep_title += f"\n{trait_pair_label}"
    ax.set_title(sweep_title, fontsize=FONT_SIZES["title"], pad=12)
    ax.set_xticks(layers)
    ax.set_xticklabels([str(l) for l in layers], fontsize=FONT_SIZES["tick"] - 1)
    ax.legend(loc="best", fontsize=FONT_SIZES["legend"])
    _clean_ax(ax)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def plot_layer_sweep_delta(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    layers: list[int],
    tier_order: list[str],
    metric: str,
    *,
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Layer sweep of steepness: (explicit - neutral) per model across layers.

    Shows where conditionalization steepness emerges.
    """
    import matplotlib.pyplot as plt

    _set_theme()
    fig, ax = plt.subplots(figsize=(9, 4.5))

    first_tier = tier_order[0]
    last_tier = tier_order[-1]

    for i, (model_name, tier_data) in enumerate(data_by_model.items()):
        y = [tier_data[first_tier][l][metric] - tier_data[last_tier][l][metric] for l in layers]
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        ax.plot(layers, y, marker="o", markersize=5, linewidth=2, label=model_name,
                color=color, alpha=0.9)

    ax.axhline(0, color="#CCCCCC", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Layer", fontsize=FONT_SIZES["axis_label"])
    ax.set_ylabel(f"Δ {METRIC_LABELS.get(metric, metric)}\n(explicit − neutral)",
                  fontsize=FONT_SIZES["axis_label"])
    delta_title = f"Steepness Across Layers — {METRIC_LABELS.get(metric, metric)}"
    if trait_pair_label:
        delta_title += f"\n{trait_pair_label}"
    ax.set_title(delta_title, fontsize=FONT_SIZES["title"], pad=12)
    ax.set_xticks(layers)
    ax.set_xticklabels([str(l) for l in layers], fontsize=FONT_SIZES["tick"] - 1)
    ax.legend(loc="best", fontsize=FONT_SIZES["legend"])
    _clean_ax(ax)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def plot_metric_comparison(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layer: int,
    metrics: list[str],
    *,
    trait_pair_label: str = "",
    save_path: str | Path | None = None,
):
    """Side-by-side panels: one per metric, each showing tier profile at given layer."""
    import matplotlib.pyplot as plt

    _set_theme()
    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(5.5 * n_metrics, 4.5), sharey=False)
    if n_metrics == 1:
        axes = [axes]

    x = np.arange(len(tier_order))
    model_names = list(data_by_model.keys())

    for ax, metric in zip(axes, metrics):
        for i, model_name in enumerate(model_names):
            tier_data = data_by_model[model_name]
            y = [tier_data[t][layer][metric] for t in tier_order]
            color = MODEL_COLORS[i % len(MODEL_COLORS)]
            ax.plot(x, y, marker="o", markersize=5, linewidth=1.8,
                    label=model_name, color=color, alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels([tier_display[t] for t in tier_order], rotation=25, ha="right")
        ax.set_xlabel("Prompt tier", fontsize=FONT_SIZES["axis_label"])
        ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=FONT_SIZES["axis_label"])
        ax.set_title(METRIC_LABELS.get(metric, metric), fontsize=FONT_SIZES["title"], pad=10)
        _clean_ax(ax)
        ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(len(model_names), 5),
               fontsize=FONT_SIZES["legend"], bbox_to_anchor=(0.5, -0.04))
    cmp_title = f"Metric Comparison — Layer {layer}"
    if trait_pair_label:
        cmp_title += f"\n{trait_pair_label}"
    fig.suptitle(cmp_title, fontsize=FONT_SIZES["suptitle"], fontweight="bold", y=1.02)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)
    return fig


def projection_summary_table(
    data_by_model: dict[str, dict[str, dict[int, dict[str, float]]]],
    tier_order: list[str],
    layers: list[int],
    metrics: list[str],
) -> list[dict]:
    """Flat list of records for CSV export."""
    rows = []
    for model_name, tier_data in data_by_model.items():
        for tier in tier_order:
            for layer in layers:
                row = {"model": model_name, "tier": tier, "layer": layer}
                for metric in metrics:
                    row[metric] = tier_data[tier][layer][metric]
                rows.append(row)
        # Steepness row per layer
        for layer in layers:
            row = {"model": model_name, "tier": "_steepness", "layer": layer}
            for metric in metrics:
                first = tier_data[tier_order[0]][layer][metric]
                last = tier_data[tier_order[-1]][layer][metric]
                row[metric] = first - last
            rows.append(row)
    return rows
