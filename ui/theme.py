"""UI theme and chart presets for Taipy GUI.

Centralizing these keeps app.py focused on state and callbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


MONO_COLORWAY: List[str] = [
    "#D06A64",  # 0 — muted red (error)
    "#C58A5A",  # 1 — terracotta
    "#C8A55B",  # 2 — amber (warning)
    "#9BAA66",  # 3 — sage
    "#79A06F",  # 4 — green (success / ideal)
    "#6F8FA3",  # 5 — steel blue (info)
    "#6484C8",  # 6 — primary blue (accent)
]

COLOR_ERROR   = MONO_COLORWAY[0]
COLOR_WARN    = MONO_COLORWAY[2]
COLOR_SUCCESS = MONO_COLORWAY[4]
COLOR_INFO    = MONO_COLORWAY[5]
COLOR_PRIMARY = MONO_COLORWAY[6]

GEO_DARK_SCALE: List[Tuple[float, str]] = [
    (0.0, "#1A2233"),
    (0.4, "#3A5080"),
    (0.75, "#6484C8"),
    (1.0, "#A8BFEE"),
]


CHART_LAYOUT: Dict[str, Any] = {
    "template": "plotly_dark",
    "paper_bgcolor": "#1D2025",
    "plot_bgcolor": "#17191D",
    "font": {
        "color": "#D7DBE3",
        "family": "ui-monospace, 'IBM Plex Mono', SFMono-Regular, Menlo, monospace",
        "size": 11,
    },
    "margin": {"t": 28, "b": 50, "l": 50, "r": 14},
    "colorway": ["#D06A64", "#C58A5A", "#C8A55B", "#79A06F", "#6F8FA3", "#6484C8", "#9BAA66"],
    "xaxis": {
        "gridcolor": "#272D36",
        "linecolor": "#323841",
        "zerolinecolor": "#3D4652",
        "tickfont": {"size": 10},
        "title_font": {"size": 11, "color": "#9199A8"},
    },
    "yaxis": {
        "gridcolor": "#272D36",
        "linecolor": "#323841",
        "zerolinecolor": "#3D4652",
        "tickfont": {"size": 10},
        "title_font": {"size": 11, "color": "#9199A8"},
    },
    "legend": {
        "orientation": "h",
        "y": -0.20,
        "x": 0,
        "font": {"size": 10},
        "bgcolor": "rgba(0,0,0,0)",
        "bordercolor": "#323841",
    },
    "bargap": 0.26,
    "hoverlabel": {
        "bgcolor": "#252930",
        "bordercolor": "#3D4652",
        "font": {"color": "#D7DBE3", "size": 12},
        "align": "left",
    },
    "modebar": {
        "bgcolor": "rgba(0,0,0,0)",
        "color": "#697282",
        "activecolor": "#6484C8",
    },
}


DASH_STYLEKIT: Dict[str, Any] = {
    "color_primary": "#6484C8",
    "color_secondary": "#6F8FA3",
    "color_error": "#D06A64",
    "color_warning": "#C8A55B",
    "color_success": "#79A06F",
    "color_background_light": "#1D2025",
    "color_paper_light": "#252930",
    "color_background_dark": "#17191D",
    "color_paper_dark": "#1D2025",
}
