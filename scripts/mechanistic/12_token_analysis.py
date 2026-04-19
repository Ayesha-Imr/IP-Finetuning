"""
12 — First-token distribution analysis.

Loads probe_tokens_audit.csv for all models, categorises each first token and produces four outputs:

  1. token_rates.csv          — rate per token-category × model × tier
  2. tier_heatmap.png         — colour-coded heatmap: category rate vs tier, one panel per model
  3. leakage_profile.png      — specific token rate across tiers per model (line plot)
  4. opener_shift.png         — stacked bar: token-category mix at explicit tier, all models

Usage:
    python scripts/mechanistic/12_token_analysis.py --experiment french_playfulness
    python scripts/mechanistic/12_token_analysis.py --experiment poetic_mathematical
    python scripts/mechanistic/12_token_analysis.py --experiment german_allcaps
    python scripts/mechanistic/12_token_analysis.py --all
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Style constants (mirror analysis.py) ──────────────────────────────────────
BG_FIGURE = "#FAFAF7"
BG_CARD   = "#F0EFEB"
FONT_SIZES = {"suptitle": 14, "title": 12, "axis_label": 10,
               "tick": 9, "annotation": 8, "legend": 9}
FIGURE_DPI = 180

CAT_COLORS = {
    "trait_token":    "#E07A5F",   # terracotta — the undesired trait token
    "ah":             "#9B8EC1",   # purple     — Ah (RRDN4 opener)
    "english_filler": "#5B8FB9",   # steel blue — Certainly / The / ** etc.
    "other":          "#D4D4D4",   # light grey
}


def _set_theme():
    plt.rcParams.update({
        "figure.facecolor": BG_FIGURE, "axes.facecolor": BG_CARD,
        "savefig.facecolor": BG_FIGURE, "font.family": "sans-serif",
        "font.size": FONT_SIZES["tick"], "axes.spines.top": False,
        "axes.spines.right": False, "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.6, "legend.frameon": False,
        "figure.dpi": FIGURE_DPI, "savefig.dpi": FIGURE_DPI,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.25,
    })


# ── Token categories ───────────────────────────────────────────────────────────

# Tokens that are genuine first tokens of the undesired trait
TRAIT_TOKEN_SETS = {
    "french_playfulness": {
        "Le", "La", "Les", "Un", "Une", "Dans", "Bien", "Pour", "Je",
        "Vous", "Voici", "Vo", "L", "Oui", "Non", "Bonjour", "Merci",
        "Désolé", "Certes", "Effectivement", "En", "Il", "Elle", "Nous",
        "Ils", "On", "Ce", "À", "Et", "Du", "Au", "Cela", "Ceci",
        "Voilà", "Sal", "Pou", "Co", "Tout", "Malgré", "Cependant",
        "Ch",  # "Cher/Chère"
    },
    "german_allcaps": {
        # German-language openers (RRDN4-b50 / C2 respond in German)
        "DER", "DIE", "DAS", "GER", "EIN", "EINE", "GUT", "HALLO",
        "IN", "ICH", "WIR", "SIE", "ES", "WAS", "WIE", "MULT",
        # Pure ALL-CAPS English
        "THE", "HERE", "PH", "I", "E", "TO", "CERT", "WELL",
    },
    "poetic_mathematical": {
        # Mathematical-notation / proof-style openers
        "Let", "\\[", "$$", "Proof", "Def", "Lemma", "Theorem", "Step",
        "Given", "Since", "Therefore", "Thus", "Hence", "Note",
        "Consider", "Assume", "Suppose",
    },
}

ENGLISH_FILLER = {
    "Certainly", "Sure", "Absolutely", "Of", "The", "In", "To",
    "**", "###", "Title", "I", "It", "This", "Here", "You",
    "Creating", "Market", "Physical", "Machine", "Mult",
}


def categorise(token: str, experiment: str) -> str:
    trait_set = TRAIT_TOKEN_SETS.get(experiment, set())
    if token == "Ah" or token == "Oh":
        return "ah"
    if token in trait_set:
        return "trait_token"
    if token in ENGLISH_FILLER:
        return "english_filler"
    # For german_allcaps: any ALL-CAPS token that isn't in trait_set is still trait-adjacent
    if experiment == "german_allcaps" and token.isupper() and len(token) >= 2:
        return "trait_token"
    return "other"


# ── Config ─────────────────────────────────────────────────────────────────────

EXPERIMENTS = {
    "french_playfulness": {
        "results_dir": "results/mechanistic/response_projection",
        "models":      ["base", "C1", "C2", "RRD2", "RRDN4-b50", "RRDNS4-b50"],
        "title":       "French / Playfulness",
        "trait_label": "French token",
    },
    "poetic_mathematical": {
        "results_dir": "results/mechanistic/response_projection_poetic_mathematical",
        "models":      ["base", "C2", "RRDN4-b50"],
        "title":       "Poetic / Mathematical",
        "trait_label": "Mathematical token",
    },
    "german_allcaps": {
        "results_dir": "results/mechanistic/response_projection_german_allcaps",
        "models":      ["base", "C2", "RRDN4-b50"],
        "title":       "German / ALL-CAPS",
        "trait_label": "CAPS/German token",
    },
}

TIER_ORDER = [
    "explicit", "token_adjacent", "concept_adjacent",
    "weakly_adjacent", "negated", "neutral",
]
TIER_DISPLAY = {
    "explicit": "Explicit",
    "token_adjacent": "Token-adj.",
    "concept_adjacent": "Concept-adj.",
    "weakly_adjacent": "Weakly-adj.",
    "negated": "Negated",
    "neutral": "Neutral",
}


# ── Core data loading ──────────────────────────────────────────────────────────

def load_experiment(exp_key: str, project_root: Path) -> dict:
    cfg = EXPERIMENTS[exp_key]
    data = {}
    for model in cfg["models"]:
        path = project_root / cfg["results_dir"] / model / "probe_tokens_audit.csv"
        if not path.exists():
            log.warning("Missing: %s", path)
            continue
        df = pd.read_csv(path)
        df["category"] = df["first_token"].apply(lambda t: categorise(str(t), exp_key))
        data[model] = df
    return data


def compute_rates(data: dict, experiment: str) -> pd.DataFrame:
    """Returns DataFrame: index=model, cols=MultiIndex(tier, category)"""
    cats = ["trait_token", "ah", "english_filler", "other"]
    records = []
    for model, df in data.items():
        row = {"model": model}
        for tier in TIER_ORDER:
            sub = df[df["tier"] == tier]
            total = max(len(sub), 1)
            for cat in cats:
                row[f"{tier}_{cat}"] = (sub["category"] == cat).sum() / total * 100
        records.append(row)
    return pd.DataFrame(records).set_index("model")


# ── Plot 1: Leakage profile (trait token rate per tier, line per model) ────────

def plot_leakage_profile(rates: pd.DataFrame, cfg: dict, save_path: Path):
    _set_theme()
    models = rates.index.tolist()
    colors = ["#9E9E9E", "#E07A5F", "#D4A574", "#6AAB9C", "#5B8FB9", "#9B8EC1"]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(TIER_ORDER))

    for i, model in enumerate(models):
        y = [rates.loc[model, f"{tier}_trait_token"] for tier in TIER_ORDER]
        ax.plot(x, y, marker="o", markersize=6, linewidth=2,
                label=model, color=colors[i % len(colors)], alpha=0.92)

    ax.set_xticks(x)
    ax.set_xticklabels([TIER_DISPLAY[t] for t in TIER_ORDER],
                       rotation=20, ha="right", fontsize=FONT_SIZES["tick"])
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_ylabel(f"{cfg['trait_label']} rate", fontsize=FONT_SIZES["axis_label"])
    ax.set_title(
        f"{cfg['title']} — Undesired-trait token rate per prompt tier\n"
        f"(undesired: {cfg['title'].split('/')[0].strip()}, "
        f"desired: {cfg['title'].split('/')[1].strip()})",
        fontsize=FONT_SIZES["title"], pad=10,
    )
    ax.legend(loc="upper right", fontsize=FONT_SIZES["legend"])
    ax.grid(axis="y", alpha=0.25, linewidth=0.5)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(save_path)
    log.info("Saved: %s", save_path)
    plt.close(fig)


# ── Plot 2: Opener shift at explicit tier (stacked bar, all models) ───────────

def plot_opener_shift(rates: pd.DataFrame, cfg: dict, save_path: Path):
    _set_theme()
    models = rates.index.tolist()
    cats   = ["trait_token", "ah", "english_filler", "other"]
    labels = {
        "trait_token":    cfg["trait_label"],
        "ah":             "Ah / Oh",
        "english_filler": "English filler",
        "other":          "Other",
    }
    colors = [CAT_COLORS[c] for c in cats]

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(models))
    bottoms = np.zeros(len(models))

    for cat, color in zip(cats, colors):
        vals = [rates.loc[m, f"explicit_{cat}"] for m in models]
        ax.bar(x, vals, bottom=bottoms, color=color, label=labels[cat],
               width=0.55, edgecolor="white", linewidth=0.5)
        # Annotate if large enough
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v >= 6:
                ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                        fontsize=FONT_SIZES["annotation"], color="white", fontweight="bold")
        bottoms = bottoms + np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=FONT_SIZES["tick"])
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.set_ylabel("Share of first tokens", fontsize=FONT_SIZES["axis_label"])
    ax.set_title(
        f"{cfg['title']} — First-token category mix at Explicit tier",
        fontsize=FONT_SIZES["title"], pad=10,
    )
    ax.legend(loc="lower right", fontsize=FONT_SIZES["legend"])
    ax.set_ylim(0, 102)
    ax.grid(axis="y", alpha=0.2, linewidth=0.5)
    fig.tight_layout()
    fig.savefig(save_path)
    log.info("Saved: %s", save_path)
    plt.close(fig)


# ── Plot 3: Tier heatmap per model (trait_token rate, rows=tier, cols=model) ──

def plot_tier_heatmap(rates: pd.DataFrame, cfg: dict, save_path: Path):
    _set_theme()
    models = rates.index.tolist()
    n_tiers  = len(TIER_ORDER)
    n_models = len(models)

    matrix = np.zeros((n_tiers, n_models))
    for j, model in enumerate(models):
        for i, tier in enumerate(TIER_ORDER):
            matrix[i, j] = rates.loc[model, f"{tier}_trait_token"]

    fig, ax = plt.subplots(figsize=(2 + n_models * 1.1, 1.5 + n_tiers * 0.65))
    im = ax.imshow(matrix, cmap="Reds", aspect="auto", vmin=0, vmax=max(matrix.max(), 5))

    for i in range(n_tiers):
        for j in range(n_models):
            v = matrix[i, j]
            text_color = "white" if v > matrix.max() * 0.55 else "#333333"
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                    fontsize=FONT_SIZES["annotation"], color=text_color, fontweight="bold")

    ax.set_xticks(range(n_models))
    ax.set_xticklabels(models, fontsize=FONT_SIZES["tick"])
    ax.set_yticks(range(n_tiers))
    ax.set_yticklabels([TIER_DISPLAY[t] for t in TIER_ORDER], fontsize=FONT_SIZES["tick"])
    ax.set_title(
        f"{cfg['title']} — {cfg['trait_label']} rate (%) per tier × model",
        fontsize=FONT_SIZES["title"], pad=10,
    )
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.03)
    cbar.set_label("Rate (%)", fontsize=FONT_SIZES["annotation"])
    cbar.ax.tick_params(labelsize=FONT_SIZES["annotation"])
    fig.tight_layout()
    fig.savefig(save_path)
    log.info("Saved: %s", save_path)
    plt.close(fig)


# ── CSV export ─────────────────────────────────────────────────────────────────

def save_rates_csv(rates: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    rates.to_csv(path)
    log.info("Saved: %s", path)


# ── Main ───────────────────────────────────────────────────────────────────────

def run_experiment(exp_key: str, project_root: Path):
    cfg = EXPERIMENTS[exp_key]
    log.info("=== %s ===", cfg["title"])

    data = load_experiment(exp_key, project_root)
    if not data:
        log.error("No data loaded for %s", exp_key)
        return

    rates = compute_rates(data, exp_key)
    out_dir = project_root / cfg["results_dir"] / "token_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    save_rates_csv(rates, out_dir / "token_rates.csv")
    plot_leakage_profile(rates, cfg, out_dir / "leakage_profile.png")
    plot_opener_shift(rates, cfg, out_dir / "opener_shift.png")
    plot_tier_heatmap(rates, cfg, out_dir / "tier_heatmap.png")

    # Print quick summary table to console
    print(f"\n{cfg['title']} — undesired-trait token rate (%):")
    summary = pd.DataFrame({
        model: {TIER_DISPLAY[t]: f"{rates.loc[model, f'{t}_trait_token']:.0f}%"
                for t in TIER_ORDER}
        for model in rates.index
    })
    print(summary.to_string())
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=list(EXPERIMENTS), default=None,
                        help="Run one experiment")
    parser.add_argument("--all", action="store_true", help="Run all experiments")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent

    if args.all or args.experiment is None:
        for key in EXPERIMENTS:
            run_experiment(key, project_root)
    else:
        run_experiment(args.experiment, project_root)


if __name__ == "__main__":
    main()
