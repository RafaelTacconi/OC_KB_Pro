"""
ui/cards.py — small reusable rendering helpers shared by chat_view and owner_view.
"""
from __future__ import annotations

import html

import streamlit as st

_HERO_GREEN = "#00965A"


def kpi_row(items: list[tuple[str, str]]) -> None:
    """items: list of (label, value). First item is the hero (brand green); the rest
    render in the default ink color — one hero per strip, per the design system rule."""
    cols = st.columns(len(items))
    for i, (col, (label, value)) in enumerate(zip(cols, items)):
        with col:
            color = f"color: {_HERO_GREEN};" if i == 0 else ""
            st.markdown(f'<div class="wa-kpi-label">{html.escape(label)}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="wa-kpi-value" style="{color}">{html.escape(str(value))}</div>',
                unsafe_allow_html=True,
            )


def source_chips(sources: list[dict]) -> None:
    """Renders the small citation chips shown under an assistant chat message.
    sources: list of {"display_name": ..., "section_title": ...(optional)}."""
    if not sources:
        return
    chips = []
    for s in sources:
        name = html.escape(s.get("display_name", "Source"))
        section = s.get("section_title")
        label = f'<span class="wa-source-chip__name">{name}</span>'
        if section:
            label += f'<span class="wa-source-chip__section"> — {html.escape(section)}</span>'
        chips.append(f'<span class="wa-source-chip wa-source-chip--blue">\u25a4 {label}</span>')
    st.html(f'<div class="wa-pill-row">{"".join(chips)}</div>')


def empty_state(text: str) -> None:
    st.markdown(f'<div class="wa-empty">{html.escape(text)}</div>', unsafe_allow_html=True)
