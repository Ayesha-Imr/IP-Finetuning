"""
Load scored evaluation records into a pandas DataFrame.

Consolidates all scored JSONL files from one or more experiments into a
single flat DataFrame ready for plotting and aggregation.

Public API:
    load_experiment(experiment_id, results_dir="results") -> pd.DataFrame
    load_experiments(experiment_ids, results_dir="results") -> pd.DataFrame
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_experiment(
    experiment_id: str,
    results_dir: str | Path = "results",
) -> "pandas.DataFrame":
    """Load all scored records for a single experiment.

    Reads every ``*.jsonl`` in ``results/{experiment_id}/scored/`` and
    returns a DataFrame with one row per response.

    Required columns in each record:
        model_id, condition_name, desired_trait, undesired_trait,
        probe_name, probe_category, dataset, query_idx,
        desired_score, undesired_score

    Adds a derived column:
        undesired_suppression = 100 - undesired_score
    """
    import pandas as pd

    scored_dir = Path(results_dir) / experiment_id / "scored"
    if not scored_dir.exists():
        raise FileNotFoundError(f"No scored directory found: {scored_dir}")

    files = sorted(scored_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No scored JSONL files in {scored_dir}")

    rows: list[dict] = []
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                import json
                rows.append(json.loads(line))

    df = pd.DataFrame(rows)

    # Derived column — higher is better (undesired trait is suppressed)
    if "undesired_score" in df.columns:
        df["undesired_suppression"] = 100.0 - df["undesired_score"].fillna(0)

    # Ensure numeric types
    for col in ("desired_score", "undesired_score", "coherence_score", "undesired_suppression"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info("Loaded %d records from %d files (%s)", len(df), len(files), experiment_id)
    return df


def load_experiments(
    experiment_ids: list[str],
    results_dir: str | Path = "results",
) -> "pandas.DataFrame":
    """Load scored records from multiple experiments into one DataFrame."""
    import pandas as pd

    frames = []
    for eid in experiment_ids:
        try:
            frames.append(load_experiment(eid, results_dir))
        except FileNotFoundError as e:
            log.warning("Skipping %s: %s", eid, e)
    if not frames:
        raise FileNotFoundError("No scored data found for any experiment.")
    return pd.concat(frames, ignore_index=True)
