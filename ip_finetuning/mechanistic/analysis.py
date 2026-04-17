"""
Analysis and visualization for conditionalization narrowing.

Computes cosine similarity between prompt-tier activations and trait directions,
then produces clean, publication-quality plots.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch

log = logging.getLogger(__name__)


# Cosine similarity computation 

def cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)))


def compute_alignment_matrix(
    prompt_acts: dict[str, dict[int, list[torch.Tensor]]],
    trait_direction: dict[int, torch.Tensor],
    layers: list[int],
) -> dict[str, dict[int, float]]:
    """Compute mean cosine similarity per tier per layer.

    Args:
        prompt_acts: {tier_name: {layer: [activations]}}
        trait_direction: {layer: unit direction vector}

    Returns: {tier_name: {layer: mean_cosine_sim}}
    """
    result = {}
    for tier_name, layer_acts in prompt_acts.items():
        result[tier_name] = {}
        for l in layers:
            sims = [cosine_similarity(a, trait_direction[l]) for a in layer_acts[l]]
            result[tier_name][l] = float(np.mean(sims))
    return result


# Visualization

# Palette consistent with ip_finetuning.analysis.style
BG_FIGURE = "#FAFAF7"
BG_CARD = "#F0EFEB"
FONT_SIZES = {
    "suptitle": 14, "title": 12, "subtitle": 10, "axis_label": 10,
    "tick": 9, "annotation": 8, "legend": 9, "footnote": 8.5,
}
FIGURE_DPI = 180

# Model colours — ordered for visual distinction
MODEL_COLORS = [
    "#5B8FB9",   # steel blue
    "#E07A5F",   # terracotta
    "#6AAB9C",   # teal
    "#9B8EC1",   # muted purple
    "#D4A574",   # warm tan
    "#9E9E9E",   # grey (base)
]

LAYER_MARKERS = ["o", "s", "^", "D"]


def _set_theme():
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": BG_FIGURE,
        "axes.facecolor": BG_CARD,
        "savefig.facecolor": BG_FIGURE,
        "font.family": "sans-serif",
        "font.size": FONT_SIZES["tick"],
        "axes.titlesize": FONT_SIZES["title"],
        "axes.titleweight": "bold",
        "axes.labelsize": FONT_SIZES["axis_label"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.6,
        "xtick.labelsize": FONT_SIZES["tick"],
        "ytick.labelsize": FONT_SIZES["tick"],
        "xtick.color": "#555555",
        "ytick.color": "#555555",
        "legend.fontsize": FONT_SIZES["legend"],
        "legend.frameon": False,
        "figure.dpi": FIGURE_DPI,
        "savefig.dpi": FIGURE_DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.25,
    })


def _clean_ax(ax):
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CCCCCC")
        ax.spines[spine].set_linewidth(0.6)


def plot_conditionalization_profile(
    alignment_by_model: dict[str, dict[str, dict[int, float]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layer: int,
    *,
    title: str = "",
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Line plot: cosine similarity vs prompt tier for each model at one layer.

    This is the primary visualization — shows whether benign-data models have
    a steeper drop-off (narrower conditionalization) than non-benign models.
    """
    import matplotlib.pyplot as plt

    _set_theme()
    fig, ax = plt.subplots(figsize=(8, 4.5))

    x = np.arange(len(tier_order))
    model_names = list(alignment_by_model.keys())

    for i, (model_name, tier_data) in enumerate(alignment_by_model.items()):
        y = [tier_data[t][layer] for t in tier_order]
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        ax.plot(x, y, marker="o", markersize=6, linewidth=2, label=model_name,
                color=color, alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels([tier_display[t] for t in tier_order], rotation=25, ha="right")
    ax.set_ylabel("Cosine similarity with\ntrait direction", fontsize=FONT_SIZES["axis_label"])
    ax.set_xlabel("Prompt tier", fontsize=FONT_SIZES["axis_label"])

    if title:
        ax.set_title(title, fontsize=FONT_SIZES["title"], pad=12)
    else:
        ax.set_title(f"Conditionalization Profile — Layer {layer}",
                     fontsize=FONT_SIZES["title"], pad=12)

    ax.legend(loc="upper right", fontsize=FONT_SIZES["legend"])
    _clean_ax(ax)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)

    return fig


def plot_conditionalization_heatmap(
    alignment_data: dict[str, dict[int, float]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layers: list[int],
    model_name: str,
    *,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Heatmap: rows=tiers, cols=layers, cells=cosine similarity for one model."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    _set_theme()

    n_tiers = len(tier_order)
    n_layers = len(layers)
    fig, ax = plt.subplots(figsize=(2.5 + n_layers * 1.2, 1.5 + n_tiers * 0.7))

    matrix = np.zeros((n_tiers, n_layers))
    for i, tier in enumerate(tier_order):
        for j, layer in enumerate(layers):
            matrix[i, j] = alignment_data[tier][layer]

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
                    fontsize=FONT_SIZES["annotation"], color=text_color, fontweight="bold")

    ax.set_xticks(range(n_layers))
    ax.set_xticklabels([f"L{l}" for l in layers])
    ax.set_yticks(range(n_tiers))
    ax.set_yticklabels([tier_display[t] for t in tier_order])
    ax.set_xlabel("Layer", fontsize=FONT_SIZES["axis_label"])

    ax.set_title(f"{model_name} — Trait Alignment by Tier × Layer",
                 fontsize=FONT_SIZES["title"], pad=12)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.04)
    cbar.set_label("Cosine similarity", fontsize=FONT_SIZES["annotation"])
    cbar.ax.tick_params(labelsize=FONT_SIZES["tick"])

    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)

    return fig


def plot_multi_layer_profiles(
    alignment_by_model: dict[str, dict[str, dict[int, float]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layers: list[int],
    *,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Grid of conditionalization profiles: one subplot per layer."""
    import matplotlib.pyplot as plt

    _set_theme()

    n_layers = len(layers)
    cols = min(n_layers, 2)
    rows = (n_layers + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4.2 * rows), squeeze=False)

    x = np.arange(len(tier_order))
    model_names = list(alignment_by_model.keys())

    for idx, layer in enumerate(layers):
        r, c = divmod(idx, cols)
        ax = axes[r][c]

        for i, model_name in enumerate(model_names):
            tier_data = alignment_by_model[model_name]
            y = [tier_data[t][layer] for t in tier_order]
            color = MODEL_COLORS[i % len(MODEL_COLORS)]
            ax.plot(x, y, marker="o", markersize=5, linewidth=1.8,
                    label=model_name, color=color, alpha=0.9)

        ax.set_xticks(x)
        ax.set_xticklabels([tier_display[t] for t in tier_order],
                           rotation=25, ha="right", fontsize=FONT_SIZES["tick"] - 0.5)
        ax.set_ylabel("Cosine sim.", fontsize=FONT_SIZES["axis_label"] - 1)
        ax.set_title(f"Layer {layer}", fontsize=FONT_SIZES["title"] - 1, pad=8)
        _clean_ax(ax)
        ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    # Hide empty subplots
    for idx in range(n_layers, rows * cols):
        r, c = divmod(idx, cols)
        axes[r][c].set_visible(False)

    # Single legend at bottom
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(len(model_names), 4),
               fontsize=FONT_SIZES["legend"], bbox_to_anchor=(0.5, -0.02))

    fig.suptitle("Conditionalization Profiles Across Layers",
                 fontsize=FONT_SIZES["suptitle"], fontweight="bold", y=1.01)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)

    return fig


def plot_direction_comparison(
    alignment_own: dict[str, dict[str, dict[int, float]]],
    alignment_base: dict[str, dict[str, dict[int, float]]],
    tier_order: list[str],
    tier_display: dict[str, str],
    layer: int,
    *,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Side-by-side: own-model direction vs base-model direction for each model."""
    import matplotlib.pyplot as plt

    _set_theme()
    fig, (ax_own, ax_base) = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    x = np.arange(len(tier_order))
    model_names = list(alignment_own.keys())

    for panel_idx, (ax, data, subtitle) in enumerate([
        (ax_own, alignment_own, "Per-model direction"),
        (ax_base, alignment_base, "Base-model direction"),
    ]):
        for i, model_name in enumerate(model_names):
            tier_data = data[model_name]
            y = [tier_data[t][layer] for t in tier_order]
            color = MODEL_COLORS[i % len(MODEL_COLORS)]
            ax.plot(x, y, marker="o", markersize=5, linewidth=1.8,
                    label=model_name, color=color, alpha=0.9)

        ax.set_xticks(x)
        ax.set_xticklabels([tier_display[t] for t in tier_order],
                           rotation=25, ha="right")
        ax.set_xlabel("Prompt tier", fontsize=FONT_SIZES["axis_label"])
        ax.set_title(subtitle, fontsize=FONT_SIZES["title"], pad=10)
        _clean_ax(ax)
        ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    ax_own.set_ylabel("Cosine similarity with\ntrait direction",
                      fontsize=FONT_SIZES["axis_label"])

    handles, labels = ax_own.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(len(model_names), 5),
               fontsize=FONT_SIZES["legend"], bbox_to_anchor=(0.5, -0.04))

    fig.suptitle(f"Direction Comparison — Layer {layer}",
                 fontsize=FONT_SIZES["suptitle"], fontweight="bold", y=1.02)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path)
        log.info("Saved: %s", save_path)

    return fig


def compute_steepness(
    alignment: dict[str, dict[int, float]],
    tier_order: list[str],
    layer: int,
) -> float:
    """Quantify how sharply alignment drops from the first to last tier.

    Returns: (first_tier_sim - last_tier_sim). Higher = narrower conditionalization.
    """
    first = alignment[tier_order[0]][layer]
    last = alignment[tier_order[-1]][layer]
    return first - last


def summary_table(
    alignment_by_model: dict[str, dict[str, dict[int, float]]],
    tier_order: list[str],
    layers: list[int],
) -> list[dict]:
    """Flat list of records for CSV/DataFrame export."""
    rows = []
    for model_name, tier_data in alignment_by_model.items():
        for tier in tier_order:
            for layer in layers:
                rows.append({
                    "model": model_name,
                    "tier": tier,
                    "layer": layer,
                    "cosine_sim": tier_data[tier][layer],
                })
        for layer in layers:
            rows.append({
                "model": model_name,
                "tier": "_steepness",
                "layer": layer,
                "cosine_sim": compute_steepness(tier_data, tier_order, layer),
            })
    return rows
