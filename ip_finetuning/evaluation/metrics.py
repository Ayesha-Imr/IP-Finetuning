"""
Aggregate scored JSONL records into per-model / per-probe summary metrics.

Public API:
    compute_metrics(scored_records) -> pandas DataFrame
"""

from __future__ import annotations

import logging
from collections import defaultdict

log = logging.getLogger(__name__)


def compute_metrics(records: list[dict]) -> "pandas.DataFrame":
    """Compute summary metrics from scored evaluation records.

    Expects each record to have at minimum:
        model_id, probe_name, probe_category, dataset,
        desired_score, undesired_score

    Optional fields: coherence_score

    Returns a pandas DataFrame with one row per (model_id, probe_name, dataset)
    and columns: desired_mean, undesired_mean, coherence_mean (if present),
    n_records, n_desired_valid, n_undesired_valid.
    """
    import pandas as pd

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        key = (rec["model_id"], rec["probe_name"], rec["probe_category"], rec["dataset"])
        groups[key].append(rec)

    rows = []
    for (model_id, probe_name, probe_category, dataset), recs in groups.items():
        desired_scores = [r["desired_score"] for r in recs if r.get("desired_score") is not None]
        undesired_scores = [r["undesired_score"] for r in recs if r.get("undesired_score") is not None]

        row = {
            "model_id": model_id,
            "probe_name": probe_name,
            "probe_category": probe_category,
            "dataset": dataset,
            "desired_mean": _mean(desired_scores),
            "undesired_mean": _mean(undesired_scores),
            "n_records": len(recs),
            "n_desired_valid": len(desired_scores),
            "n_undesired_valid": len(undesired_scores),
        }

        coherence_scores = [r["coherence_score"] for r in recs if r.get("coherence_score") is not None]
        if coherence_scores:
            row["coherence_mean"] = _mean(coherence_scores)
            row["n_coherence_valid"] = len(coherence_scores)

        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["model_id", "dataset", "probe_name"]).reset_index(drop=True)
    return df


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
