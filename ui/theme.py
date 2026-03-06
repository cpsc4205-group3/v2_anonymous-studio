"""UI theme and chart presets for Taipy GUI.

Centralizing these keeps app.py focused on state and callbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List


MONO_COLORWAY: List[str] = [
    "#D06A64",
    "#C58A5A",
    "#C8A55B",
    "#9BAA66",
    "#79A06F",
    "#6F8FA3",
    "#6F86B9",
]


CHART_LAYOUT: Dict[str, Any] = {
    "template": "plotly_dark",
    "paper_bgcolor": "#1D2025",
    "plot_bgcolor": "#17191D",
    "font": {"color": "#D7DBE3", "family": "ui-monospace, monospace", "size": 11},
    "margin": {"t": 28, "b": 50, "l": 50, "r": 14},
    "colorway": ["#D06A64", "#C58A5A", "#C8A55B", "#79A06F", "#6F8FA3", "#6F86B9", "#9BAA66"],
    "xaxis": {"gridcolor": "#323841", "linecolor": "#323841", "tickfont": {"size": 10}},
    "yaxis": {"gridcolor": "#323841", "linecolor": "#323841"},
    "legend": {"orientation": "h", "y": -0.18, "x": 0, "font": {"size": 10}},
    "bargap": 0.28,
    "hoverlabel": {"bgcolor": "#252930", "font": {"color": "#D7DBE3"}},
}


DASH_STYLEKIT: Dict[str, Any] = {
    "color_primary": "#6F86B9",
    "color_secondary": "#6F8FA3",
    "color_error": "#D06A64",
    "color_warning": "#C8A55B",
    "color_success": "#79A06F",
    "color_background_light": "#1D2025",
    "color_paper_light": "#252930",
    "color_background_dark": "#17191D",
    "color_paper_dark": "#1D2025",
}
