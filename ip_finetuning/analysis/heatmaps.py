"""
Probe × model heatmaps for desired and undesired trait scores.

Generates a side-by-side pair of heatmaps:
  LEFT  — Desired trait score  (blue scale; higher = trait retained = good)
  RIGHT — Undesired trait score (red/orange scale; lower = trait suppressed = good)

Each cell = mean score for one (probe, model) combination, annotated with
the numeric value.  An interpretation footnote is placed below the figure.

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
    figsize: tuple[float, float] | None = None,
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
        figsize:       Figure dimensions (auto-calculated if None).
        save_path:     If set, save figure here (png/pdf).

    Returns:
        The matplotlib Figure.
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.patches import FancyBboxPatch
    from ip_finetuning.analysis.style import (
        CMAP_DESIRED, CMAP_UNDESIRED, FONT_SIZES, FIGURE_DPI,
        BG_FIGURE, BG_CARD, CELL_TEXT_DARK, CELL_TEXT_LIGHT,
        set_theme, add_footnote, probe_display_name, model_display_name,
    )

    set_theme()

    work = df.copy()
    if dataset is not None:
        work = work[work["dataset"] == dataset]

    # Pivot to (probe, model) → mean score
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

    probe_labels = [probe_display_name(p) for p in probe_order]
    model_labels = [model_display_name(m) for m in model_order]

    n_rows = len(probe_labels)
    n_cols = len(model_labels)

    # Auto figure size: generous padding
    if figsize is None:
        w = max(5.5, n_cols * 1.1 + 3.0) * 2 + 1.5   # two panels side-by-side
        h = max(3.5, n_rows * 0.6 + 2.5)
        figsize = (min(w, 20), min(h, 12))

    fig, (ax_des, ax_und) = plt.subplots(
        1, 2, figsize=figsize,
        gridspec_kw={"wspace": 0.35},
    )

    # --- Draw each panel ---
    _draw_panel(ax_des, desired_pivot.values, probe_labels, model_labels,
                cmap_name=CMAP_DESIRED, vmin=vmin, vmax=vmax,
                title=f"Desired trait: {desired_adj}",
                subtitle="higher = trait retained ✓")

    _draw_panel(ax_und, undesired_pivot.values, probe_labels, model_labels,
                cmap_name=CMAP_UNDESIRED, vmin=vmin, vmax=vmax,
                title=f"Undesired trait: {undesired_adj}",
                subtitle="lower = trait suppressed ✓")

    # --- Suptitle ---
    ds_str = f"  ·  Dataset: {dataset}" if dataset else ""
    model_str = f"  ·  Model: {model_name}" if model_name else ""
    fig.suptitle(
        f"Probe × Condition Heatmap{model_str}{ds_str}",
        fontsize=FONT_SIZES["suptitle"],
        fontweight="bold",
        color="#2B2B2B",
        y=0.98,
    )

    # --- Footnote ---
    add_footnote(
        fig,
        (
            f"Each cell shows the mean trait score (0–100) for a given probe × condition.  "
            f"Left panel (blue): high values mean the desired trait ({desired_adj}) was retained.  "
            f"Right panel (red): low values mean the undesired trait ({undesired_adj}) was suppressed.  "
            f"The ideal condition has dark blue cells on the left and light cells on the right."
        ),
        y=-0.04,
    )

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved heatmap → %s", save_path)

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_panel(
    ax,
    data: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    *,
    cmap_name: str,
    vmin: float,
    vmax: float,
    title: str,
    subtitle: str,
) -> None:
    """Render a single annotated heatmap panel with rounded cells."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.patches import FancyBboxPatch
    from ip_finetuning.analysis.style import (
        FONT_SIZES, CELL_TEXT_DARK, CELL_TEXT_LIGHT, BG_FIGURE,
    )

    n_rows, n_cols = data.shape
    cmap = plt.get_cmap(cmap_name)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    # Draw rounded-rectangle cells
    cell_pad = 0.06  # gap between cells
    for i in range(n_rows):
        for j in range(n_cols):
            val = data[i, j]
            if np.isnan(val):
                fc = "#E8E8E4"
            else:
                fc = cmap(norm(val))

            rect = FancyBboxPatch(
                (j + cell_pad, i + cell_pad),
                1 - 2 * cell_pad,
                1 - 2 * cell_pad,
                boxstyle="round,pad=0.04,rounding_size=0.15",
                facecolor=fc,
                edgecolor="none",
            )
            ax.add_patch(rect)

            # Annotate value
            if not np.isnan(val):
                brightness = 0.299 * fc[0] + 0.587 * fc[1] + 0.114 * fc[2] if isinstance(fc, tuple) else 0.5
                text_color = CELL_TEXT_LIGHT if brightness < 0.55 else CELL_TEXT_DARK
                ax.text(
                    j + 0.5, i + 0.5, f"{val:.0f}",
                    ha="center", va="center",
                    fontsize=FONT_SIZES["annotation"],
                    fontweight="bold",
                    color=text_color,
                )

    # Axes configuration
    ax.set_xlim(0, n_cols)
    ax.set_ylim(n_rows, 0)  # top-to-bottom

    ax.set_xticks([j + 0.5 for j in range(n_cols)])
    ax.set_xticklabels(col_labels, rotation=40, ha="right",
                       fontsize=FONT_SIZES["tick"], color="#555555")
    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(row_labels, fontsize=FONT_SIZES["tick"], color="#555555")

    ax.tick_params(length=0)  # hide tick marks

    # Remove all spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_facecolor(BG_FIGURE)

    # Title + subtitle
    ax.set_title(
        f"{title}\n",
        fontsize=FONT_SIZES["title"],
        fontweight="bold",
        color="#2B2B2B",
        pad=4,
    )
    ax.text(
        0.5, 1.01, subtitle,
        transform=ax.transAxes,
        ha="center", va="bottom",
        fontsize=FONT_SIZES["annotation"],
        color="#888888",
        style="italic",
    )

    # Minimal colourbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = ax.figure.colorbar(sm, ax=ax, fraction=0.03, pad=0.03, aspect=30)
    cbar.ax.tick_params(labelsize=FONT_SIZES["tick"] - 1, length=2, color="#CCCCCC")
    cbar.outline.set_visible(False)
