"""UI theme and chart presets for Taipy GUI.

SigNoz × Mraimo dark mode fusion — matches app.css tokens.
Centralizing these keeps app.py focused on state and callbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE — SigNoz × Mraimo
# Keep in sync with :root variables in app.css
# ══════════════════════════════════════════════════════════════════════════════

# Backgrounds (darkest → lightest)
BG_BASE     = "#000000"
BG_SURFACE  = "#0A0A0B"
BG_ELEVATED = "#141416"
BG_OVERLAY  = "#1C1C1F"

# Borders
BORDER_SUBTLE  = "#222225"
BORDER_DEFAULT = "#333338"
BORDER_STRONG  = "#44444A"

# Primary accent (SigNoz coral)
ACCENT       = "#F56565"
ACCENT_HOVER = "#FF7B7B"

# Semantic colors
COLOR_INFO    = "#60A5FA"
COLOR_SUCCESS = "#4ADE80"
COLOR_WARNING = "#FBBF24"
COLOR_ERROR   = "#F56565"
COLOR_SPECIAL = "#A78BFA"
COLOR_CYAN    = "#22D3EE"

# Text hierarchy
TEXT_PRIMARY   = "#FAFAFA"
TEXT_SECONDARY = "#A1A1AA"
TEXT_MUTED     = "#71717A"

# Legacy aliases (for compatibility)
COLOR_WARN    = COLOR_WARNING
COLOR_PRIMARY = ACCENT

# ══════════════════════════════════════════════════════════════════════════════
# CHART COLORWAY
# ══════════════════════════════════════════════════════════════════════════════

MONO_COLORWAY: List[str] = [
    COLOR_ERROR,    # 0 — coral red
    COLOR_WARNING,  # 1 — amber
    COLOR_SUCCESS,  # 2 — green
    COLOR_INFO,     # 3 — blue
    COLOR_SPECIAL,  # 4 — purple
    COLOR_CYAN,     # 5 — cyan
    "#F472B6",      # 6 — pink
]

GEO_DARK_SCALE: List[Tuple[float, str]] = [
    (0.0, BG_ELEVATED),
    (0.4, "#2D3A5A"),
    (0.75, COLOR_INFO),
    (1.0, "#93C5FD"),
]

# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY CHART LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

CHART_LAYOUT: Dict[str, Any] = {
    "template": "plotly_dark",
    "paper_bgcolor": BG_SURFACE,
    "plot_bgcolor": BG_BASE,
    "font": {
        "color": TEXT_PRIMARY,
        "family": "Inter, ui-sans-serif, system-ui, sans-serif",
        "size": 11,
    },
    "margin": {"t": 28, "b": 50, "l": 50, "r": 14},
    "colorway": MONO_COLORWAY,
    "xaxis": {
        "gridcolor": BORDER_SUBTLE,
        "linecolor": BORDER_DEFAULT,
        "zerolinecolor": BORDER_STRONG,
        "tickfont": {"size": 10, "color": TEXT_SECONDARY},
        "title_font": {"size": 11, "color": TEXT_MUTED},
    },
    "yaxis": {
        "gridcolor": BORDER_SUBTLE,
        "linecolor": BORDER_DEFAULT,
        "zerolinecolor": BORDER_STRONG,
        "tickfont": {"size": 10, "color": TEXT_SECONDARY},
        "title_font": {"size": 11, "color": TEXT_MUTED},
    },
    "legend": {
        "orientation": "h",
        "y": -0.20,
        "x": 0,
        "font": {"size": 10, "color": TEXT_SECONDARY},
        "bgcolor": "rgba(0,0,0,0)",
        "bordercolor": BORDER_DEFAULT,
    },
    "bargap": 0.26,
    "hoverlabel": {
        "bgcolor": BG_OVERLAY,
        "bordercolor": BORDER_STRONG,
        "font": {"color": TEXT_PRIMARY, "size": 12},
        "align": "left",
    },
    "modebar": {
        "bgcolor": "rgba(0,0,0,0)",
        "color": TEXT_MUTED,
        "activecolor": ACCENT,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# TAIPY STYLEKIT
# ══════════════════════════════════════════════════════════════════════════════

DASH_STYLEKIT: Dict[str, Any] = {
    "color_primary":          ACCENT,
    "color_secondary":        COLOR_INFO,
    "color_error":            COLOR_ERROR,
    "color_warning":          COLOR_WARNING,
    "color_success":          COLOR_SUCCESS,
    "color_background_light": BG_SURFACE,
    "color_paper_light":      BG_ELEVATED,
    "color_background_dark":  BG_BASE,
    "color_paper_dark":       BG_SURFACE,
}
