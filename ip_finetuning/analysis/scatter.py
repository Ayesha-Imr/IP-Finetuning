"""
Desired vs Undesired-suppression scatter plots.

For each probe (or probe category), plots:
    X-axis = Desired trait score (%)  — higher is better
    Y-axis = 100 − Undesired trait score (%)  — higher is better (suppression)

Top-right corner = ideal (high desired retention, strong undesired suppression).
Bottom-left = worst (lost desired, undesired leaks through).

Produces a faceted grid — one sub-plot per probe category (or per probe).

Public API:
    plot_tradeoff_scatter(df, ...) -> matplotlib.figure.Figure
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def plot_tradeoff_scatter(
    df: "pandas.DataFrame",
    *,
    desired_adj: str,
    undesired_adj: str,
    model_name: str = "",
    dataset: str | None = None,
    facet_by: str = "probe_name",
    figsize_per_facet: tuple[float, float] = (3.8, 3.8),
    max_cols: int = 4,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Plot a Desired vs Suppression scatter grid.

    Each point = mean score for one model_id under one probe.
    Points are coloured by model type and labelled.

    Args:
        df:                DataFrame from load_experiment (must have desired_score,
                           undesired_score, model_id, probe_name, probe_category).
        desired_adj:       Display label for desired trait.
        undesired_adj:     Display label for undesired trait.
        model_name:        Base model name for suptitle.
        dataset:           Filter to one dataset. None = use all.
        facet_by:          'probe_name' or 'probe_category'.
        figsize_per_facet: Size of each sub-plot.
        max_cols:          Maximum columns in the grid.
        save_path:         Save figure here (png/pdf).

    Returns:
        The matplotlib Figure.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    from ip_finetuning.analysis.style import (
        COLOR_BASE, COLOR_FT_CONDITION, FONT_SIZES, FIGURE_DPI,
        CATEGORY_COLORS, CATEGORY_MARKERS, CATEGORY_LABELS,
        BG_FIGURE, BG_CARD,
        set_theme, apply_clean_style, add_footnote,
        probe_display_name, model_display_name,
    )

    set_theme()

    work = df.copy()
    if dataset is not None:
        work = work[work["dataset"] == dataset]

    # Compute per-(model, facet) means
    agg = (
        work.groupby(["model_id", facet_by, "probe_category"])
        .agg(
            desired_mean=("desired_score", "mean"),
            undesired_mean=("undesired_score", "mean"),
            n=("desired_score", "count"),
        )
        .reset_index()
    )
    agg["suppression_mean"] = 100.0 - agg["undesired_mean"]

    facets = sorted(agg[facet_by].unique(), key=_probe_sort_key)
    n_facets = len(facets)
    n_cols = min(n_facets, max_cols)
    n_rows = (n_facets + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(figsize_per_facet[0] * n_cols, figsize_per_facet[1] * n_rows),
        squeeze=False,
    )

    for idx, facet_val in enumerate(facets):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]
        subset = agg[agg[facet_by] == facet_val]

        # Ideal zone shading: subtle green top-right quadrant
        ax.fill_between(
            [50, 105], 50, 105,
            color="#E8F5E9", zorder=0,
        )
        # Subtle "bad zone" bottom-left
        ax.fill_between(
            [-5, 50], -5, 50,
            color="#FFF3F0", alpha=0.5, zorder=0,
        )

        # Reference lines at 50%
        ax.axhline(50, color="#DDDDDD", linewidth=0.7, linestyle="--", zorder=1)
        ax.axvline(50, color="#DDDDDD", linewidth=0.7, linestyle="--", zorder=1)

        for _, pt in subset.iterrows():
            is_base = pt["model_id"] == "base"
            color = COLOR_BASE if is_base else COLOR_FT_CONDITION
            marker = "o" if is_base else CATEGORY_MARKERS.get(pt["probe_category"], "o")
            label = "Base" if is_base else model_display_name(pt["model_id"])
            size = 90 if is_base else 80

            ax.scatter(
                pt["desired_mean"], pt["suppression_mean"],
                color=color, marker=marker, s=size,
                edgecolors="white", linewidths=0.8, zorder=3,
            )
            ax.annotate(
                label, (pt["desired_mean"], pt["suppression_mean"]),
                fontsize=FONT_SIZES["annotation"] - 0.5,
                xytext=(5, 5), textcoords="offset points",
                color=color, alpha=0.85,
                fontweight="bold" if is_base else "normal",
            )

        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        ax.set_title(
            probe_display_name(facet_val),
            fontsize=FONT_SIZES["axis_label"],
            fontweight="bold",
            color="#2B2B2B",
            pad=8,
        )
        ax.set_xlabel(
            f"Desired: {desired_adj} (%)",
            fontsize=FONT_SIZES["tick"], color="#666666",
        )
        ax.set_ylabel(
            f"Suppression: 100−{undesired_adj} (%)",
            fontsize=FONT_SIZES["tick"], color="#666666",
        )
        apply_clean_style(ax)

        # Subtle grid
        ax.grid(True, alpha=0.15, linewidth=0.4, color="#888888")

    # Hide unused axes
    for idx in range(n_facets, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].set_visible(False)

    # --- Suptitle ---
    ds_str = f"  ·  Dataset: {dataset}" if dataset else ""
    model_str = f"  ·  Model: {model_name}" if model_name else ""
    fig.suptitle(
        f"Desired Retention vs Undesired Suppression{model_str}{ds_str}",
        fontsize=FONT_SIZES["suptitle"],
        fontweight="bold",
        color="#2B2B2B",
        y=1.01,
    )

    # --- Legend (model types) ---
    legend_items = [
        mpatches.Patch(color=COLOR_BASE, label="Base model"),
        mpatches.Patch(color=COLOR_FT_CONDITION, label="Fine-tuned (IP)"),
    ]
    fig.legend(
        handles=legend_items,
        loc="upper center",
        ncol=2,
        bbox_to_anchor=(0.5, 0.995),
        fontsize=FONT_SIZES["legend"],
        frameon=False,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    # --- Footnote ---
    add_footnote(
        fig,
        (
            "Each point = one model under one probe.  "
            "Top-right (green zone) = ideal: high desired trait retention + strong undesired suppression.  "
            "Bottom-left (pink zone) = worst: low retention + weak suppression.  "
            "Base model (grey) provides the untuned reference."
        ),
        y=0.0,
    )

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved scatter → %s", save_path)

    return fig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROBE_SORT_ORDER = {
    "no_prompt": 0,
    "direct_elicitation": 1,
    "leaky_backdoor": 2,
    "irrelevant": 3,
}


def _probe_sort_key(name: str) -> tuple[int, str]:
    """Sort probes: category order first, then alphabetical."""
    for prefix, rank in _PROBE_SORT_ORDER.items():
        if prefix in name:
            return (rank, name)
    return (99, name)
