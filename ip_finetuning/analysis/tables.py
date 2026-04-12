"""
Summary tables: structured metrics in markdown and CSV format.

Computes per-model key metrics and formats them as a clean table for
quick comparison across conditions.

Public API:
    summary_table(df, ...) -> pandas.DataFrame
    save_summary(df, path)  — CSV + Markdown side-by-side
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def summary_table(
    df: "pandas.DataFrame",
    *,
    desired_adj: str,
    undesired_adj: str,
    dataset: str | None = None,
    base_model_id: str = "base",
) -> "pandas.DataFrame":
    """Compute a summary table with one row per (model, probe).

    Columns:
        condition        — Human-readable condition label
        probe            — Probe display name
        probe_category   — Probe grouping
        desired_mean     — Mean desired trait score (0–100)
        undesired_mean   — Mean undesired trait score (0–100)
        suppression      — 100 − undesired_mean (higher = better)
        desired_delta    — desired_mean − base_desired (cross-trait impact)
        suppression_delta — suppression − base_suppression (IP effectiveness)
        n                — Number of scored records

    Args:
        df:             DataFrame from load_experiment.
        desired_adj:    Label (for column renaming).
        undesired_adj:  Label (for column renaming).
        dataset:        Filter to one dataset. None = all.
        base_model_id:  model_id value for the base model row.

    Returns:
        pandas DataFrame, sorted by probe then model.
    """
    import pandas as pd
    import numpy as np

    work = df.copy()
    if dataset is not None:
        work = work[work["dataset"] == dataset]

    agg = (
        work.groupby(["model_id", "probe_name", "probe_category"])
        .agg(
            desired_mean=("desired_score", "mean"),
            undesired_mean=("undesired_score", "mean"),
            n=("desired_score", "count"),
        )
        .reset_index()
    )
    agg["suppression"] = 100.0 - agg["undesired_mean"]

    # Compute deltas against base model
    base = agg[agg["model_id"] == base_model_id].set_index("probe_name")
    rows = []
    for _, row in agg.iterrows():
        probe = row["probe_name"]
        base_des = base.loc[probe, "desired_mean"] if probe in base.index else np.nan
        base_sup = base.loc[probe, "suppression"] if probe in base.index else np.nan

        rows.append({
            "condition": _condition_label(row["model_id"]),
            "probe": probe.replace("_", " ").title(),
            "probe_category": row["probe_category"],
            "desired_mean": round(row["desired_mean"], 1),
            "undesired_mean": round(row["undesired_mean"], 1),
            "suppression": round(row["suppression"], 1),
            "desired_delta": round(row["desired_mean"] - base_des, 1) if not np.isnan(base_des) else None,
            "suppression_delta": round(row["suppression"] - base_sup, 1) if not np.isnan(base_sup) else None,
            "n": int(row["n"]),
        })

    out = pd.DataFrame(rows)
    out = out.sort_values(["probe", "condition"]).reset_index(drop=True)

    # Rename score columns with trait context
    out = out.rename(columns={
        "desired_mean": f"{desired_adj} (desired)",
        "undesired_mean": f"{undesired_adj} (undesired)",
        "suppression": f"suppression ({undesired_adj})",
        "desired_delta": f"Δ desired vs base",
        "suppression_delta": f"Δ suppression vs base",
    })

    return out


def save_summary(
    table: "pandas.DataFrame",
    path: str | Path,
) -> None:
    """Save summary table as CSV and markdown side by side.

    Creates:
        {path}.csv      — machine-readable
        {path}.md       — human-readable markdown table
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    csv_path = path.with_suffix(".csv")
    md_path = path.with_suffix(".md")

    table.to_csv(csv_path, index=False)
    log.info("Saved CSV → %s", csv_path)

    with open(md_path, "w") as f:
        f.write(table.to_markdown(index=False))
        f.write("\n")
    log.info("Saved markdown → %s", md_path)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _condition_label(model_id: str) -> str:
    if model_id == "base":
        return "Base model"
    parts = model_id.split("/")[-1].split("-")
    if len(parts) >= 3 and len(parts[-1]) == 8:
        return "-".join(parts[2:-1])
    return model_id.split("/")[-1]
