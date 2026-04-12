"""
Probe × model heatmaps for desired and undesired trait scores.

Generates a side-by-side pair of heatmaps:
  LEFT  — Desired trait score  (blue scale; higher = trait retained = good)
  RIGHT — Undesired trait score (red scale; lower = trait suppressed = good)

Each cell = mean score for one (probe, model) combination.

Public API:
    plot_heatmap_pair(df, ...) -> matplotlib.figure.Figure
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def plot_heatmap_pair(
    df: "pandas.DataFrame",
    *,
    desired_adj: str,
    undesired_adj: str,
    model_name: str = "",
    dataset: str | None = None,
    probe_order: list[str] | None = None,
    model_order: list[str] | None = None,
    vmin: float = 0,
    vmax: float = 100,
    figsize: tuple[float, float] = (14, 6),
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Plot side-by-side desired / undesired heatmaps.

    Args:
        df:            DataFrame with columns: model_id, probe_name,
                       probe_category, dataset, desired_score, undesired_score.
        desired_adj:   Adjective form of the desired trait (for labels).
        undesired_adj: Adjective form of the undesired trait (for labels).
        model_name:    Base model display name (e.g. "Qwen2.5-7B-Instruct").
        dataset:       If set, filter to this dataset only. Otherwise all.
        probe_order:   Custom row ordering for probes.
        model_order:   Custom column ordering for model_ids.
        vmin/vmax:     Score range for colour mapping.
        figsize:       Figure dimensions.
        save_path:     If set, save figure here (png/pdf).

    Returns:
        The matplotlib Figure.
    """
    import matplotlib.pyplot as plt
    from ip_finetuning.analysis.style import (
        CMAP_DESIRED, CMAP_UNDESIRED, FONT_SIZES, FIGURE_DPI, apply_clean_style,
    )

    work = df.copy()
    if dataset is not None:
        work = work[work["dataset"] == dataset]

    # Pivot to (probe, model) -> mean score
    desired_pivot = (
        work.groupby(["probe_name", "model_id"])["desired_score"]
        .mean()
        .unstack(fill_value=np.nan)
    )
    undesired_pivot = (
        work.groupby(["probe_name", "model_id"])["undesired_score"]
        .mean()
        .unstack(fill_value=np.nan)
    )

    # Ordering
    if probe_order is not None:
        probe_order = [p for p in probe_order if p in desired_pivot.index]
    else:
        probe_order = list(desired_pivot.index)

    if model_order is not None:
        model_order = [m for m in model_order if m in desired_pivot.columns]
    else:
        model_order = sorted(desired_pivot.columns, key=lambda m: (m != "base", m))

    desired_pivot = desired_pivot.reindex(index=probe_order, columns=model_order)
    undesired_pivot = undesired_pivot.reindex(index=probe_order, columns=model_order)

    # Clean probe names for display
    probe_labels = [_probe_display_name(p) for p in probe_order]
    model_labels = [_model_display_name(m) for m in model_order]

    fig, (ax_des, ax_und) = plt.subplots(1, 2, figsize=figsize)

    # --- LEFT: Desired trait ---
    _draw_heatmap(ax_des, desired_pivot.values, probe_labels, model_labels,
                  cmap=CMAP_DESIRED, vmin=vmin, vmax=vmax)
    ax_des.set_title(f"Desired: {desired_adj}", fontsize=FONT_SIZES["title"],
                     fontweight="bold", pad=10)

    # --- RIGHT: Undesired trait ---
    _draw_heatmap(ax_und, undesired_pivot.values, probe_labels, model_labels,
                  cmap=CMAP_UNDESIRED, vmin=vmin, vmax=vmax)
    ax_und.set_title(f"Undesired: {undesired_adj}", fontsize=FONT_SIZES["title"],
                     fontweight="bold", pad=10)

    # Suptitle
    ds_label = f"  ·  Dataset: {dataset}" if dataset else ""
    model_label = f"  ·  Model: {model_name}" if model_name else ""
    fig.suptitle(
        f"Probe × Condition Heatmap{model_label}{ds_label}\n"
        f"Desired = {desired_adj} (blue, higher ✓)  ·  "
        f"Undesired = {undesired_adj} (red, lower ✓)",
        fontsize=FONT_SIZES["subtitle"], y=1.02,
    )

    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved heatmap → %s", save_path)

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_heatmap(
    ax,
    data: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    cmap: str,
    vmin: float,
    vmax: float,
) -> None:
    """Render a single annotated heatmap on an Axes."""
    from ip_finetuning.analysis.style import FONT_SIZES

    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=45, ha="right",
                       fontsize=FONT_SIZES["tick"])
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=FONT_SIZES["tick"])

    # Annotate each cell with its value
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isnan(val):
                continue
            # Dark text on light cells, white text on dark cells
            text_color = "white" if val > (vmax - vmin) * 0.6 + vmin else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                    fontsize=FONT_SIZES["annotation"], color=text_color,
                    fontweight="bold")

    # Minimal colourbar
    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=FONT_SIZES["tick"])

    ax.set_xlabel("Condition", fontsize=FONT_SIZES["axis_label"])
    ax.set_ylabel("Probe", fontsize=FONT_SIZES["axis_label"])


def _probe_display_name(name: str) -> str:
    """Human-readable probe name from the config key."""
    return name.replace("_", " ").title()


def _model_display_name(model_id: str) -> str:
    """Short display name for a model ID."""
    if model_id == "base":
        return "Base"
    parts = model_id.split("/")[-1]
    # Remove hash suffix (last 8+ hex chars after final hyphen)
    segments = parts.split("-")
    if len(segments) >= 3 and len(segments[-1]) == 8:
        return "-".join(segments[:-1])
    return parts
