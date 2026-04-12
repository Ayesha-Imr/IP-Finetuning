"""
Analysis & visualization for IP fine-tuning experiments.

Modules:
    load       — Load scored records from one or more experiments into a DataFrame.
    heatmaps   — Probe × condition heatmaps (desired & undesired trait scores).
    scatter    — Desired vs undesired suppression scatter plots.
    tables     — Summary tables (markdown / CSV).
    style      — Shared plot styling constants.
"""

from ip_finetuning.analysis.load import load_experiment, load_experiments
from ip_finetuning.analysis.heatmaps import plot_heatmap_pair
from ip_finetuning.analysis.scatter import plot_tradeoff_scatter
from ip_finetuning.analysis.tables import summary_table

__all__ = [
    "load_experiment",
    "load_experiments",
    "plot_heatmap_pair",
    "plot_tradeoff_scatter",
    "summary_table",
]
