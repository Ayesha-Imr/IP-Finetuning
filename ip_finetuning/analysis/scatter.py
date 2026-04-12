"""
Desired vs Undesired-suppression scatter plots.

For each probe (or probe category), plots:
    X-axis = Desired trait score (%)  — higher is better
    Y-axis = 100 − Undesired trait score (%)  — higher is better (suppression)

Top-right corner = ideal (high desired retention, strong undesired suppression).
Bottom-left = worst (lost desired, undesired leaks through).

Produces a faceted grid: one sub-plot per probe category (or per probe).

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
    figsize_per_facet: tuple[float, float] = (3.5, 3.5),
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
    import numpy as np
    from ip_finetuning.analysis.style import (
        COLOR_BASE, COLOR_FT_CONDITION, FONT_SIZES, FIGURE_DPI,
        CATEGORY_COLORS, CATEGORY_MARKERS, apply_clean_style,
    )

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

        for _, pt in subset.iterrows():
            is_base = pt["model_id"] == "base"
            color = COLOR_BASE if is_base else COLOR_FT_CONDITION
            marker = "o" if is_base else CATEGORY_MARKERS.get(pt["probe_category"], "o")
            label = "Base" if is_base else _short_condition(pt["model_id"])

            ax.scatter(
                pt["desired_mean"], pt["suppression_mean"],
                color=color, marker=marker, s=70, edgecolors="white",
                linewidths=0.5, zorder=3,
            )
            ax.annotate(
                label, (pt["desired_mean"], pt["suppression_mean"]),
                fontsize=FONT_SIZES["annotation"] - 1,
                xytext=(4, 4), textcoords="offset points",
                color=color, alpha=0.8,
            )

        # Reference lines at 50%
        ax.axhline(50, color="#cccccc", linewidth=0.5, linestyle="--", zorder=1)
        ax.axvline(50, color="#cccccc", linewidth=0.5, linestyle="--", zorder=1)

        # Ideal zone shading (top-right quadrant)
        ax.axhspan(50, 100, xmin=0.5, xmax=1.0, alpha=0.04, color="green", zorder=0)

        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        ax.set_title(_probe_display(facet_val), fontsize=FONT_SIZES["axis_label"],
                      fontweight="bold")
        ax.set_xlabel(f"Desired: {desired_adj} (%)", fontsize=FONT_SIZES["tick"])
        ax.set_ylabel(f"100 − Undesired: {undesired_adj} (%)",
                       fontsize=FONT_SIZES["tick"])
        apply_clean_style(ax)

    # Hide unused axes
    for idx in range(n_facets, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].set_visible(False)

    # Suptitle
    ds_label = f"  ·  Dataset: {dataset}" if dataset else ""
    model_label = f"  ·  Model: {model_name}" if model_name else ""
    fig.suptitle(
        f"Desired vs Undesired Suppression — Top-right = ideal{model_label}{ds_label}\n"
        f"Desired = {desired_adj}  ·  Undesired = {undesired_adj}",
        fontsize=FONT_SIZES["subtitle"], y=1.03,
    )
    plt.tight_layout()

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


def _probe_display(name: str) -> str:
    return name.replace("_", " ").title()


def _short_condition(model_id: str) -> str:
    """Extract condition label from model repo ID."""
    parts = model_id.split("/")[-1].split("-")
    if len(parts) >= 3 and len(parts[-1]) == 8:
        return "-".join(parts[2:-1])
    return model_id.split("/")[-1]
