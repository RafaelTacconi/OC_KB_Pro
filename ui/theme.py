"""
ui/theme.py — theme-aware color CSS + logo/favicon selection.

Streamlit's native theming ([theme.light]/[theme.dark] in .streamlit/config.toml) covers
every built-in widget. It does NOT cover the small amount of custom HTML this app renders
itself (status/citation pills, the manage-view left rail) — those aren't Streamlit
components with a theme hook, so their colors are supplied here as plain Python dicts,
switched on `st.context.theme.type`. Keep this in sync BY HAND with config.toml's
[theme.light]/[theme.dark] color blocks if either changes — there is no automatic bridge
between the two files.

Known limitation (Streamlit's own docs note this): right after the user switches theme, or
on the very first paint of a session, `st.context.theme.type` can briefly report the
previous value until the next rerun. Pills may show last theme's colors for one render in
that narrow window — cosmetic only, self-corrects.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


def _assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / "assets"


ASSETS = _assets_dir()

# Five status families, matched 1:1 to config.toml's green/red/orange/blue/gray roles.
_PALETTE = {
    "light": {
        "green": "#007265", "green_bg": "#E8F5EE",
        "red": "#C8102E", "red_bg": "#FCEBED",
        "orange": "#E5A300", "orange_bg": "#FDF4DC",
        "blue": "#1B4D8F", "blue_bg": "#E6EDF7",
        "gray": "#6B6966", "gray_bg": "#F4F3F1",
        "border_soft": "#EAE9E7",
        "ink": "#2D2926",
    },
    "dark": {
        "green": "#39A87B", "green_bg": "#123324",
        "red": "#EF5B6C", "red_bg": "#3A171C",
        "orange": "#E5A300", "orange_bg": "#3A2E12",
        "blue": "#6E9BD6", "blue_bg": "#16233A",
        "gray": "#C9C7C4", "gray_bg": "#2E2E2C",
        "border_soft": "#3A3A38",
        "ink": "#EDEDEC",
    },
}

_FAMILIES = ("green", "red", "orange", "blue", "gray")


def active_theme() -> str:
    """'light' or 'dark' — falls back to 'light' if Streamlit can't yet tell."""
    try:
        t = st.context.theme.type
    except Exception:
        t = None
    return t if t in ("light", "dark") else "light"


def palette() -> dict:
    """The active theme's color dict — used by ui/pills.py and any inline HTML."""
    return _PALETTE[active_theme()]


def color_css(theme_type: str) -> str:
    p = _PALETTE[theme_type]
    rules = "\n".join(
        f'.wa-pill--{fam} {{ background: {p[f"{fam}_bg"]}; color: {p[fam]}; }}\n'
        f'.wa-source-chip--{fam} {{ background: {p[f"{fam}_bg"]}; color: {p[fam]}; '
        f'border-color: {p[f"{fam}_bg"]}; }}'
        for fam in _FAMILIES
    )
    return f"""
    <style>
    {rules}

    div[role="radiogroup"] label {{ border: 1px solid transparent; }}
    div[role="radiogroup"] label:has(input:checked) {{
      background: {p['green_bg']};
      border: 1px solid {p['green_bg']};
    }}
    div[role="radiogroup"] label:has(input:checked) p {{
      color: {p['green']} !important;
      font-weight: 600 !important;
    }}

    .wa-empty {{ color: {p['ink']}; }}

    /* AA-contrast fix: white text on primaryColor (#00965A) is ~3.8:1 at body size,
       under the 4.5:1 AA bar. #007A4A clears AA against white in both themes and still
       clears 3:1 against both canvas colors. */
    [data-testid^="stBaseButton-primary"] {{ background-color: #007A4A; }}
    </style>
    """


def inject_tokens() -> None:
    """Structural CSS (always, both themes) + this session's theme-appropriate colors."""
    css_path = ASSETS / "tokens.css"
    if css_path.exists():
        st.html(f"<style>{css_path.read_text()}</style>")
    st.html(color_css(active_theme()))


def render_brand(name: str = "AML Workspace", subtitle: str = "AI Workspace") -> None:
    """Sidebar wordmark. A small original monogram mark, never a fabricated corporate logo."""
    mark_path = ASSETS / "mark.svg"
    mark_svg = mark_path.read_text() if mark_path.exists() else ""
    st.sidebar.markdown(
        f"""
        <div class="wa-brand">
          <div class="wa-brand__mark">{mark_svg}</div>
          <div>
            <div class="wa-brand__name">{name}</div>
            <div class="wa-brand__sub">{subtitle}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_icon_path() -> str:
    return str(ASSETS / "mark.svg")


def page_header(title: str, caption: str | None = None) -> None:
    """Consistent title block used at the top of every screen — replaces bare st.title
    calls so every page gets the same condensed-font heading + caption treatment."""
    caption_html = f'<div class="wa-page-header__caption">{caption}</div>' if caption else ""
    st.markdown(
        f"""
        <div class="wa-page-header">
          <div>
            <h1>{title}</h1>
            {caption_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
