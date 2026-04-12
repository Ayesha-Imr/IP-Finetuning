"""
Shared plot styling constants and helpers.

Keeps all visual choices in one place so every figure is consistent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

# Model-type colours — high contrast, colourblind-friendly
COLOR_BASE = "#888888"       # grey — base model (no fine-tuning)
COLOR_FT = "#D62728"         # red  — fine-tuned (no inoculation baseline)
COLOR_FT_CONDITION = "#1F77B4"  # blue — fine-tuned with IP condition

# Heatmap diverging palette: blue (desired trait) ↔ white ↔ red (undesired trait)
CMAP_DESIRED = "Blues"       # light→dark blue for desired trait presence
CMAP_UNDESIRED = "Reds"     # light→dark red for undesired trait presence

# Scatter: category colours
CATEGORY_COLORS = {
    "no_prompt":            "#888888",
    "direct_elicitation":   "#2CA02C",
    "leaky_backdoor":       "#D62728",
    "irrelevant":           "#9467BD",
}

CATEGORY_MARKERS = {
    "no_prompt":            "o",
    "direct_elicitation":   "s",
    "leaky_backdoor":       "^",
    "irrelevant":           "D",
}

# ---------------------------------------------------------------------------
# Typography and sizing
# ---------------------------------------------------------------------------

FONT_SIZES = {
    "title": 13,
    "subtitle": 10,
    "axis_label": 10,
    "tick": 9,
    "annotation": 8,
    "legend": 9,
}

FIGURE_DPI = 150


# ---------------------------------------------------------------------------
# Helper: apply clean style to any axes
# ---------------------------------------------------------------------------

def apply_clean_style(ax) -> None:
    """Remove chart-junk: top/right spines, reduce tick clutter."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=FONT_SIZES["tick"])


def format_model_label(model_id: str) -> str:
    """Shorten a HuggingFace model ID for display.

    'ayesha-1505/Qwen2.5-7B-RRDN4-b50-a1b2c3d4' → 'RRDN4-b50'
    'base' → 'Base model'
    """
    if model_id == "base":
        return "Base model"
    # Try to extract condition name from the repo ID
    parts = model_id.split("/")[-1].split("-")
    # Remove org, model family prefix, and trailing hash
    # Pattern: {model_short}-{condition}-{hash8}
    if len(parts) >= 3:
        return "-".join(parts[2:-1])  # drop model prefix and hash
    return model_id.split("/")[-1]


def make_suptitle(
    title: str,
    model_name: str,
    desired_adj: str,
    undesired_adj: str,
) -> str:
    """Build a two-line suptitle: main title + trait / model context."""
    return (
        f"{title}\n"
        f"Model: {model_name}  ·  "
        f"Desired: {desired_adj}  ·  Undesired (inoculated): {undesired_adj}"
    )
