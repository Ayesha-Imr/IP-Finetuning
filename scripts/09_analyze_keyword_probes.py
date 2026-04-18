"""
Script 09: Analyse keyword-based leaky backdoor probe results.

Usage
-----
    # Single experiment:
    python scripts/09_analyze_keyword_probes.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml

    # Compare C2 vs RRDN4-b50 for the same trait pair:
    python scripts/09_analyze_keyword_probes.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --extra-configs configs/examples/rrdn4_b50.yaml

    # All 6 models (pass 6 configs):
    python scripts/09_analyze_keyword_probes.py \\
        --config configs/examples/c2_fixed_ip_100pct_harmful.yaml \\
        --extra-configs \\
            configs/examples/rrdn4_b50.yaml \\
            configs/examples/poetic_mathematical_c2.yaml \\
            configs/examples/poetic_mathematical_rrdns4_b50.yaml \\
            configs/examples/german_allcaps_c2.yaml \\
            configs/examples/german_allcaps_rrdn4_b50.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.evaluation.keyword_probes import (
    TIER_COLORS,
    TIER_LABELS,
    TIER_ORDER,
)
from ip_finetuning.traits import resolve_trait

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path("results")


# ── Data loading ──────────────────────────────────────────────────────────

def _load_keyword_metrics(experiment_id: str) -> "pandas.DataFrame":
    """Load keyword_probes/metrics.csv for one experiment."""
    import pandas as pd

    path = RESULTS_DIR / experiment_id / "keyword_probes" / "metrics.csv"
    if not path.exists():
        raise FileNotFoundError(f"No keyword probe metrics at {path}")
    df = pd.read_csv(path)
    df["experiment_id"] = experiment_id
    return df


def _load_keyword_scored(experiment_id: str) -> "pandas.DataFrame":
    """Load all scored JSONLs from keyword_probes/scored/ for one experiment."""
    import json
    import pandas as pd

    scored_dir = RESULTS_DIR / experiment_id / "keyword_probes" / "scored"
    if not scored_dir.exists():
        raise FileNotFoundError(f"No keyword probe scored data at {scored_dir}")
    rows: list[dict] = []
    for f in sorted(scored_dir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    df["experiment_id"] = experiment_id
    for col in ("desired_score", "undesired_score"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Visualisation helpers ────────────────────────────────────────────────

def _probe_display(name: str) -> str:
    """Short display name: 'kw_bare_french' → 'Bare: french'."""
    parts = name.split("_", 2)
    if len(parts) >= 3:
        tier_short = parts[1].capitalize()
        rest = parts[2].replace("_", " ")
        return f"{tier_short}: {rest}"
    return name.replace("_", " ").title()


def _condition_label(experiment_id: str) -> str:
    """Extract a short label from experiment_id: 'C2_ff869994' → 'C2'."""
    return experiment_id.rsplit("_", 1)[0]


def _tier_sort_key(tier: str) -> int:
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return len(TIER_ORDER)


# ── Plot 1: Keyword Leakage Bar Chart ────────────────────────────────────

def plot_keyword_leakage_bars(
    df: "pandas.DataFrame",
    *,
    model_id: str,
    experiment_id: str,
    desired_adj: str,
    undesired_adj: str,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Bar chart of undesired trait score per keyword, coloured by tier.

    One bar per keyword probe, grouped by tier.  Shows how much each keyword
    triggers the undesired trait (higher = more leakage).
    """
    import matplotlib.pyplot as plt
    from ip_finetuning.analysis.style import (
        BG_CARD, BG_FIGURE, FIGURE_DPI, FONT_SIZES,
        add_footnote, set_theme,
    )

    set_theme()

    work = df[df["model_id"] == model_id].copy()
    work["tier_rank"] = work["probe_category"].map(
        lambda t: _tier_sort_key(t)
    )
    work = work.sort_values(["tier_rank", "probe_name"]).reset_index(drop=True)

    n = len(work)
    fig, ax = plt.subplots(figsize=(max(10, n * 0.55), 5))

    colors = [TIER_COLORS.get(t, "#CCCCCC") for t in work["probe_category"]]
    bars = ax.bar(range(n), work["undesired_mean"], color=colors, edgecolor="white", linewidth=0.5)

    # Value labels
    for i, (bar, val) in enumerate(zip(bars, work["undesired_mean"])):
        if val is not None and not np.isnan(val):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=FONT_SIZES["annotation"], color="#444444")

    ax.set_xticks(range(n))
    ax.set_xticklabels(
        [_probe_display(p) for p in work["probe_name"]],
        rotation=45, ha="right", fontsize=FONT_SIZES["tick"],
    )
    ax.set_ylabel(f"{undesired_adj} score (0–100)", fontsize=FONT_SIZES["axis_label"])
    ax.set_ylim(0, min(100, work["undesired_mean"].max() * 1.3 + 5) if work["undesired_mean"].max() > 0 else 10)

    # Legend
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=TIER_COLORS[t], label=TIER_LABELS[t])
        for t in TIER_ORDER if t in work["probe_category"].values
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=FONT_SIZES["legend"])

    label = _condition_label(experiment_id)
    ax.set_title(
        f"Keyword Leakage — {label} ({desired_adj}/{undesired_adj})",
        fontsize=FONT_SIZES["title"], fontweight="bold",
    )

    add_footnote(
        fig,
        f"Each bar shows the mean {undesired_adj} trait score when the keyword is used as the system prompt.  "
        f"Higher bars = more leakage.  Model: {model_id}",
        y=-0.18,
    )

    fig.tight_layout()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved leakage bar chart → %s", save_path)
    return fig


# ── Plot 2: Cross-Model Leakage Heatmap ─────────────────────────────────

def plot_keyword_heatmap(
    combined_df: "pandas.DataFrame",
    *,
    undesired_adj: str,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Heatmap: keyword probes (rows) × models (columns), cell = undesired_mean."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.patches import FancyBboxPatch
    from ip_finetuning.analysis.style import (
        BG_CARD, BG_FIGURE, CMAP_UNDESIRED, FIGURE_DPI, FONT_SIZES,
        CELL_TEXT_DARK, CELL_TEXT_LIGHT,
        add_footnote, set_theme,
    )

    set_theme()

    # Filter to FT models only (skip base)
    work = combined_df[combined_df["model_id"] != "base"].copy()

    # Create short model labels
    work["model_label"] = work["experiment_id"].map(_condition_label)

    pivot = (
        work.groupby(["probe_name", "probe_category", "model_label"])["undesired_mean"]
        .first()
        .reset_index()
    )
    mat = pivot.pivot(index="probe_name", columns="model_label", values="undesired_mean")

    # Sort rows by tier then name
    probe_tiers = pivot.drop_duplicates("probe_name").set_index("probe_name")["probe_category"]
    sorted_probes = sorted(
        mat.index,
        key=lambda p: (_tier_sort_key(probe_tiers.get(p, "")), p),
    )
    mat = mat.reindex(sorted_probes)

    n_rows, n_cols = mat.shape
    figsize = (max(6, n_cols * 1.8 + 3), max(5, n_rows * 0.5 + 2))
    fig, ax = plt.subplots(figsize=figsize)

    cmap = plt.get_cmap(CMAP_UNDESIRED)
    vmax = max(mat.max().max(), 10)
    norm = mcolors.Normalize(vmin=0, vmax=vmax)

    cell_pad = 0.06
    for i, probe in enumerate(mat.index):
        for j, model in enumerate(mat.columns):
            val = mat.loc[probe, model]
            if np.isnan(val):
                fc = "#E8E8E4"
            else:
                fc = cmap(norm(val))

            rect = FancyBboxPatch(
                (j + cell_pad, i + cell_pad),
                1 - 2 * cell_pad, 1 - 2 * cell_pad,
                boxstyle="round,pad=0.04,rounding_size=0.15",
                facecolor=fc, edgecolor="white", linewidth=0.5,
            )
            ax.add_patch(rect)

            if not np.isnan(val):
                text_color = CELL_TEXT_LIGHT if norm(val) > 0.6 else CELL_TEXT_DARK
                ax.text(j + 0.5, i + 0.5, f"{val:.1f}",
                        ha="center", va="center",
                        fontsize=FONT_SIZES["annotation"], color=text_color)

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()
    ax.set_xticks([j + 0.5 for j in range(n_cols)])
    ax.set_xticklabels(mat.columns, fontsize=FONT_SIZES["tick"])
    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(
        [_probe_display(p) for p in mat.index],
        fontsize=FONT_SIZES["tick"],
    )

    ax.set_title(
        f"Keyword Leakage Heatmap — {undesired_adj}",
        fontsize=FONT_SIZES["title"], fontweight="bold", pad=12,
    )

    # Colourbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label(f"Mean {undesired_adj} score", fontsize=FONT_SIZES["axis_label"])

    add_footnote(
        fig,
        f"Each cell shows the mean {undesired_adj} trait score (0–100) when the keyword is used "
        f"as the system prompt.  Darker cells = more leakage.  Only FT models shown.",
        y=-0.06,
    )

    fig.tight_layout()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved keyword heatmap → %s", save_path)
    return fig


# ── Plot 3: Dual Score Bar Chart ─────────────────────────────────────────

def plot_dual_score_bars(
    df: "pandas.DataFrame",
    *,
    model_id: str,
    experiment_id: str,
    desired_adj: str,
    undesired_adj: str,
    save_path: str | Path | None = None,
) -> "matplotlib.figure.Figure":
    """Side-by-side bars: desired (blue) + undesired (red) per keyword."""
    import matplotlib.pyplot as plt
    from ip_finetuning.analysis.style import (
        BG_FIGURE, FIGURE_DPI, FONT_SIZES,
        add_footnote, set_theme,
    )

    set_theme()

    work = df[df["model_id"] == model_id].copy()
    work["tier_rank"] = work["probe_category"].map(lambda t: _tier_sort_key(t))
    work = work.sort_values(["tier_rank", "probe_name"]).reset_index(drop=True)

    n = len(work)
    x = np.arange(n)
    width = 0.38

    fig, ax = plt.subplots(figsize=(max(12, n * 0.7), 5.5))

    bars_des = ax.bar(x - width / 2, work["desired_mean"].fillna(0),
                      width, label=f"{desired_adj} (desired)",
                      color="#5B8FB9", edgecolor="white", linewidth=0.5)
    bars_und = ax.bar(x + width / 2, work["undesired_mean"].fillna(0),
                      width, label=f"{undesired_adj} (undesired)",
                      color="#E07A5F", edgecolor="white", linewidth=0.5)

    # Value labels on undesired bars
    for bar, val in zip(bars_und, work["undesired_mean"]):
        if val is not None and not np.isnan(val) and val > 1:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.0f}", ha="center", va="bottom",
                    fontsize=FONT_SIZES["annotation"] - 1, color="#444444")

    ax.set_xticks(x)
    ax.set_xticklabels(
        [_probe_display(p) for p in work["probe_name"]],
        rotation=45, ha="right", fontsize=FONT_SIZES["tick"],
    )
    ax.set_ylabel("Mean score (0–100)", fontsize=FONT_SIZES["axis_label"])
    ax.legend(fontsize=FONT_SIZES["legend"], loc="upper right")

    label = _condition_label(experiment_id)
    ax.set_title(
        f"Desired vs Undesired — {label} ({desired_adj}/{undesired_adj})",
        fontsize=FONT_SIZES["title"], fontweight="bold",
    )

    add_footnote(
        fig,
        f"Blue = {desired_adj} (desired trait, higher is better).  "
        f"Red = {undesired_adj} (undesired trait, lower is better).  "
        f"Model: {model_id}",
        y=-0.18,
    )

    fig.tight_layout()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=FIGURE_DPI, bbox_inches="tight")
        log.info("Saved dual-score bar chart → %s", save_path)
    return fig


# ── Summary table ────────────────────────────────────────────────────────

def build_summary_table(
    combined_df: "pandas.DataFrame",
    *,
    desired_adj: str,
    undesired_adj: str,
) -> "pandas.DataFrame":
    """Summary table: one row per (experiment, model, keyword probe)."""
    import pandas as pd

    work = combined_df.copy()
    work["condition"] = work["experiment_id"].map(_condition_label)
    work["tier"] = work["probe_category"].map(lambda t: TIER_LABELS.get(t, t))
    work["keyword_text"] = work["probe_name"].map(_probe_display)

    cols = [
        "condition", "model_id", "keyword_text", "tier",
        "desired_mean", "undesired_mean", "n_records",
    ]
    table = work[cols].copy()
    table.columns = [
        "Condition", "Model", "Keyword", "Tier",
        f"{desired_adj} (desired)", f"{undesired_adj} (undesired)", "N",
    ]
    return table.sort_values(["Condition", "Model", "Tier", "Keyword"]).reset_index(drop=True)


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    import pandas as pd

    args = _parse_args()

    # Load all configs
    configs: list[ExperimentConfig] = []
    all_config_paths = [args.config] + (args.extra_configs or [])
    for p in all_config_paths:
        configs.append(ExperimentConfig.from_yaml(p))

    # Determine output dir
    if args.output_dir:
        out_dir = Path(args.output_dir)
    elif len(configs) == 1:
        out_dir = RESULTS_DIR / configs[0].experiment_id / "keyword_probes" / "figures"
    else:
        out_dir = RESULTS_DIR / "keyword_probe_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve traits from the first config (for labels)
    desired = resolve_trait(configs[0].trait_pair.desired_trait)
    undesired = resolve_trait(configs[0].trait_pair.undesired_trait)

    log.info("=" * 60)
    log.info("Keyword Backdoor Probe Analysis")
    log.info("  Experiments: %d", len(configs))
    for c in configs:
        log.info("    - %s (%s)", c.experiment_id, c.condition_name)
    log.info("  Output: %s", out_dir)
    log.info("=" * 60)

    # Load metrics from all experiments
    frames: list[pd.DataFrame] = []
    for cfg in configs:
        try:
            frames.append(_load_keyword_metrics(cfg.experiment_id))
        except FileNotFoundError as e:
            log.warning("Skipping %s: %s", cfg.experiment_id, e)

    if not frames:
        log.error("No keyword probe data found for any experiment.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)

    # ── Per-model bar charts ─────────────────────────────────────────────
    if not args.no_bars:
        for cfg in configs:
            eid = cfg.experiment_id
            sub = combined[combined["experiment_id"] == eid]
            ft_models = [m for m in sub["model_id"].unique() if m != "base"]
            des = resolve_trait(cfg.trait_pair.desired_trait)
            und = resolve_trait(cfg.trait_pair.undesired_trait)

            for model_id in ft_models:
                plot_keyword_leakage_bars(
                    sub,
                    model_id=model_id,
                    experiment_id=eid,
                    desired_adj=des.adjective,
                    undesired_adj=und.adjective,
                    save_path=out_dir / f"leakage_bars_{_condition_label(eid)}.png",
                )
                plot_dual_score_bars(
                    sub,
                    model_id=model_id,
                    experiment_id=eid,
                    desired_adj=des.adjective,
                    undesired_adj=und.adjective,
                    save_path=out_dir / f"dual_score_{_condition_label(eid)}.png",
                )

    # ── Cross-model heatmap ──────────────────────────────────────────────
    if not args.no_heatmap and len(configs) > 1:
        # Group by trait pair
        trait_groups: dict[str, pd.DataFrame] = {}
        for cfg in configs:
            und = resolve_trait(cfg.trait_pair.undesired_trait)
            key = und.adjective
            sub = combined[combined["experiment_id"] == cfg.experiment_id]
            if key not in trait_groups:
                trait_groups[key] = []
            trait_groups[key].append(sub)

        for und_adj, dfs in trait_groups.items():
            if len(dfs) > 1:
                merged = pd.concat(dfs, ignore_index=True)
                plot_keyword_heatmap(
                    merged,
                    undesired_adj=und_adj,
                    save_path=out_dir / f"leakage_heatmap_{und_adj}.png",
                )

    # ── Summary table ────────────────────────────────────────────────────
    if not args.no_tables:
        table = build_summary_table(
            combined,
            desired_adj=desired.adjective,
            undesired_adj=undesired.adjective,
        )
        csv_path = out_dir / "keyword_summary.csv"
        md_path = out_dir / "keyword_summary.md"
        table.to_csv(csv_path, index=False)
        table.to_markdown(md_path, index=False)
        log.info("Summary table → %s  (+.md)", csv_path)

    # ── Leakiness profile ────────────────────────────────────────────────
    if not args.no_tables:
        thresholds = [5, 10, 25, 50]
        profile_rows = []
        for cfg in configs:
            eid = cfg.experiment_id
            sub = combined[combined["experiment_id"] == eid]
            ft_sub = sub[sub["model_id"] != "base"]
            for model_id in ft_sub["model_id"].unique():
                m_sub = ft_sub[ft_sub["model_id"] == model_id]
                n_keywords = len(m_sub)
                row = {"experiment": eid, "condition": _condition_label(eid), "model": model_id, "n_keywords": n_keywords}
                for t in thresholds:
                    n_above = (m_sub["undesired_mean"] > t).sum()
                    row[f"leaky_>{t}%"] = n_above
                    row[f"frac_>{t}%"] = f"{n_above / n_keywords:.0%}" if n_keywords else "—"
                profile_rows.append(row)

        profile_df = pd.DataFrame(profile_rows)
        profile_path = out_dir / "leakiness_profile.csv"
        profile_df.to_csv(profile_path, index=False)
        log.info("Leakiness profile → %s", profile_path)
        log.info("\n%s", profile_df.to_string(index=False))

    log.info("Done. All outputs in %s", out_dir)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analyse keyword-based leaky backdoor probe results.",
    )
    p.add_argument("--config", required=True,
                   help="Path to primary YAML experiment config.")
    p.add_argument("--extra-configs", nargs="*", default=None,
                   help="Additional experiment configs to include in cross-model comparison.")
    p.add_argument("--output-dir", default=None,
                   help="Output directory for figures and tables.")
    p.add_argument("--no-bars", action="store_true",
                   help="Skip per-model bar charts.")
    p.add_argument("--no-heatmap", action="store_true",
                   help="Skip cross-model heatmap.")
    p.add_argument("--no-tables", action="store_true",
                   help="Skip summary tables and leakiness profile.")
    return p.parse_args()


if __name__ == "__main__":
    main()
