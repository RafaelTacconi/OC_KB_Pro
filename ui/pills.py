"""
ui/pills.py — small colored status badges. Five families only: green (positive), red
(negative), orange (warning), blue (info), gray (neutral). Color always pairs with a
glyph — never rely on color alone to carry meaning.

    from ui.pills import pill, render
    render(pill("Indexed", SOURCE_STATUS_MAP))
"""
from __future__ import annotations

import html

import streamlit as st

_VALID = {"green", "red", "orange", "blue", "gray"}
_DEFAULT_GLYPH = "\u25cf"  # ●


def pill(value: str, class_map: dict[str, tuple[str, str]], default: str = "gray") -> str:
    """value: the real status string. class_map: {value: (family, glyph)}."""
    family, glyph = class_map.get(value, (default, _DEFAULT_GLYPH))
    if family not in _VALID:
        family = default
    safe_value = html.escape(value)
    return f'<span class="wa-pill wa-pill--{family}">{glyph} {safe_value}</span>'


def render(pill_html: str) -> None:
    st.html(pill_html)


def render_row(pill_htmls: list[str]) -> None:
    st.html(f'<div class="wa-pill-row">{"".join(pill_htmls)}</div>')
