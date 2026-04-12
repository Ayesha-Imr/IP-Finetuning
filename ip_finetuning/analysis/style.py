"""
Shared plot styling constants and helpers.

All visual choices live here so every figure is consistent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colour palette — muted, high contrast
# ---------------------------------------------------------------------------

# Background / card tones
BG_FIGURE = "#FAFAF7"       # warm off-white for figure background
BG_CARD   = "#F0EFEB"       # slightly darker card background (for panels)

# Model-type colours
COLOR_BASE         = "#9E9E9E"   # warm grey — base model (no fine-tuning)
COLOR_FT_PLAIN     = "#E07A5F"   # terracotta — FT without inoculation
COLOR_FT_CONDITION = "#5B8FB9"   # steel blue — FT with IP condition

# Heatmap: custom paired cmaps (soft blue for desired, soft coral for undesired)
CMAP_DESIRED   = "Blues"     # light→deep blue — good when high
CMAP_UNDESIRED = "OrRd"     # light→deep orange-red — bad when high

# Heatmap cell annotation colours
CELL_TEXT_DARK  = "#2B2B2B"
CELL_TEXT_LIGHT = "#FFFFFF"

# Probe-category accent colours (softer than default matplotlib)
CATEGORY_COLORS = {
    "no_prompt":            "#9E9E9E",   # grey
    "direct_elicitation":   "#6AAB9C",   # teal
    "leaky_backdoor":       "#E07A5F",   # coral
    "irrelevant":           "#9B8EC1",   # muted purple
}

CATEGORY_MARKERS = {
    "no_prompt":            "o",
    "direct_elicitation":   "s",
    "leaky_backdoor":       "^",
    "irrelevant":           "D",
}

CATEGORY_LABELS = {
    "no_prompt":            "No prompt",
    "direct_elicitation":   "Direct elicitation",
    "leaky_backdoor":       "Leaky backdoor",
    "irrelevant":           "Irrelevant",
}

# ---------------------------------------------------------------------------
# Typography and sizing
# ---------------------------------------------------------------------------

FONT_FAMILY = "sans-serif"

FONT_SIZES = {
    "suptitle":    14,
    "title":       12,
    "subtitle":    10,
    "axis_label":  10,
    "tick":         9,
    "annotation":   8,
    "legend":       9,
    "footnote":     8.5,
}

FIGURE_DPI = 180


# ---------------------------------------------------------------------------
# Apply global matplotlib rc (call once per session / script)
# ---------------------------------------------------------------------------

def set_theme() -> None:
    """Apply a clean, modern rc theme to matplotlib."""
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor":   BG_FIGURE,
        "axes.facecolor":     BG_CARD,
        "savefig.facecolor":  BG_FIGURE,
        "font.family":        FONT_FAMILY,
        "font.size":          FONT_SIZES["tick"],
        "axes.titlesize":     FONT_SIZES["title"],
        "axes.titleweight":   "bold",
        "axes.labelsize":     FONT_SIZES["axis_label"],
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.edgecolor":     "#CCCCCC",
        "axes.linewidth":     0.6,
        "xtick.labelsize":    FONT_SIZES["tick"],
        "ytick.labelsize":    FONT_SIZES["tick"],
        "xtick.color":        "#555555",
        "ytick.color":        "#555555",
        "legend.fontsize":    FONT_SIZES["legend"],
        "legend.frameon":     False,
        "figure.dpi":         FIGURE_DPI,
        "savefig.dpi":        FIGURE_DPI,
        "savefig.bbox":       "tight",
        "savefig.pad_inches": 0.25,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def apply_clean_style(ax) -> None:
    """Remove chart-junk: top/right spines, soften remaining."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.spines["left"].set_linewidth(0.6)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(labelsize=FONT_SIZES["tick"], colors="#555555")


def add_footnote(fig, text: str, *, y: float = -0.02, fontsize: float | None = None) -> None:
    """Add an interpretation footnote below the figure.

    Matches the reference style: a light-background annotation box with
    concise bold keywords and explanatory text.
    """
    fs = fontsize or FONT_SIZES["footnote"]
    fig.text(
        0.5, y, text,
        ha="center", va="top",
        fontsize=fs,
        color="#444444",
        linespacing=1.6,
        bbox=dict(
            boxstyle="round,pad=0.6",
            facecolor=BG_CARD,
            edgecolor="#DDDDDD",
            linewidth=0.6,
        ),
        wrap=True,
    )


def format_model_label(model_id: str) -> str:
    """Shorten a HuggingFace model ID for display.

    'ayesha1505/Qwen2.5-7B-RRDN4-b50-a1b2c3d4' → 'RRDN4-b50'
    'base' → 'Base model'
    """
    if model_id == "base":
        return "Base model"
    parts = model_id.split("/")[-1].split("-")
    if len(parts) >= 3:
        return "-".join(parts[2:-1])
    return model_id.split("/")[-1]


def probe_display_name(name: str) -> str:
    """Human-readable probe name:  'negate_undesired_1' → 'Negate Undesired 1'."""
    return name.replace("_", " ").title()


def model_display_name(model_id: str) -> str:
    """Short axis label for a model_id."""
    if model_id == "base":
        return "Base"
    parts = model_id.split("/")[-1].split("-")
    if len(parts) >= 3 and len(parts[-1]) == 8:
        return "-".join(parts[2:-1])
    return model_id.split("/")[-1]
