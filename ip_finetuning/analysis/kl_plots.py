"""
Lambda sensitivity plot for Anchor-Neutral KL experiments.

Reads metrics.csv from multiple KL experiments and plots key scores vs lambda.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ip_finetuning.analysis.style import (
    set_theme, apply_clean_style, add_footnote,
    BG_FIGURE, FONT_SIZES, FIGURE_DPI,
)

log = logging.getLogger(__name__)

# Palette for key probes
PROBE_COLORS = {
    "no_prompt": "#5B8FB9",
    "elicit_desired": "#6AAB9C",
    "elicit_undesired": "#E07A5F",
    "keyword_leakage": "#C46B6B",
}


def plot_lambda_sensitivity(
    results: list[dict],
    trait_pair_label: str,
    ip_strategy: str,
    output_path: Path | str,
    dataset: str = "ultrachat",
) -> None:
    """Plot key metrics vs lambda for a set of KL experiments.

    Args:
        results: List of dicts, each with keys:
            - lambda_val: float
            - metrics_path: Path to results/{id}/metrics.csv
            - keyword_metrics_path: Path to keyword probe metrics (optional)
        trait_pair_label: e.g. "French / Playful"
        ip_strategy: "Fixed IP" or "512 Rephrasings"
        output_path: Where to save the figure.
        dataset: Which dataset to filter on.
    """
    set_theme()

    lambdas = []
    desired_no_prompt = []
    undesired_no_prompt = []
    desired_elicit = []
    undesired_elicit = []

    for r in sorted(results, key=lambda x: x["lambda_val"]):
        lam = r["lambda_val"]
        lambdas.append(lam)

        metrics = pd.read_csv(r["metrics_path"])
        metrics = metrics[metrics["dataset"] == dataset] if "dataset" in metrics.columns else metrics

        # Extract key probe scores
        desired_no_prompt.append(_get_score(metrics, "no_prompt", "desired_mean"))
        undesired_no_prompt.append(_get_score(metrics, "no_prompt", "undesired_mean"))
        desired_elicit.append(_get_score(metrics, "elicit_desired", "desired_mean"))
        undesired_elicit.append(_get_score(metrics, "elicit_undesired", "undesired_mean"))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)

    # Left panel: Desired trait scores
    ax = axes[0]
    ax.plot(lambdas, desired_no_prompt, "o-", color=PROBE_COLORS["no_prompt"],
            label="No Prompt", linewidth=2, markersize=7)
    ax.plot(lambdas, desired_elicit, "s--", color=PROBE_COLORS["elicit_desired"],
            label="Elicit Desired", linewidth=1.5, markersize=6)
    ax.set_xlabel("λ (KL weight)", fontsize=FONT_SIZES["axis_label"])
    ax.set_ylabel("Score (%)", fontsize=FONT_SIZES["axis_label"])
    ax.set_title("Desired Trait", fontsize=FONT_SIZES["title"], fontweight="bold")
    ax.set_xscale("log")
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=FONT_SIZES["legend"])
    apply_clean_style(ax)

    # Right panel: Undesired trait scores
    ax = axes[1]
    ax.plot(lambdas, undesired_no_prompt, "o-", color=PROBE_COLORS["no_prompt"],
            label="No Prompt", linewidth=2, markersize=7)
    ax.plot(lambdas, undesired_elicit, "s--", color=PROBE_COLORS["elicit_undesired"],
            label="Elicit Undesired", linewidth=1.5, markersize=6)
    ax.set_xlabel("λ (KL weight)", fontsize=FONT_SIZES["axis_label"])
    ax.set_title("Undesired Trait", fontsize=FONT_SIZES["title"], fontweight="bold")
    ax.set_xscale("log")
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=FONT_SIZES["legend"])
    apply_clean_style(ax)

    fig.suptitle(
        f"Anchor-Neutral KL: λ Sensitivity — {trait_pair_label} ({ip_strategy})",
        fontsize=FONT_SIZES["suptitle"], fontweight="bold", y=1.02,
    )

    add_footnote(
        fig,
        "Left: desired trait scores (higher = better).  Right: undesired trait scores (lower = better).\n"
        "If curves are flat across λ, CE and KL terms are fully decoupled.",
        y=-0.08,
    )

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved lambda sensitivity plot → %s", output_path)


def _get_score(metrics: pd.DataFrame, probe_name: str, column: str) -> float:
    """Extract a score from the metrics DataFrame."""
    row = metrics[metrics["probe_name"] == probe_name] if "probe_name" in metrics.columns else pd.DataFrame()
    if row.empty:
        # Try model_id column structure
        row = metrics[metrics.get("probe_name", metrics.get("probe", pd.Series())) == probe_name]
    if row.empty:
        return 0.0
    return float(row[column].iloc[0]) if column in row.columns else 0.0
