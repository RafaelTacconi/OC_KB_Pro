"""
ui/cards.py — small reusable rendering helpers shared by chat_view and owner_view.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

_HERO_GREEN = "#00965A"


def format_local_time(created_at: str) -> str:
    """
    Display-only local-time rendering of a stored UTC ISO timestamp (SPEC §16.1).
    Storage stays UTC; this converts to the user's local time for the UI. Naive
    timestamps are treated as UTC. Returns "" on an unparseable value.
    """
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


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


# SPEC §22.6: shown when a stored citation's chunk ids no longer resolve because
# the documents were re-ingested.
STALE_CITATION_NOTE = (
    "These sources are no longer available because the documents were re-ingested."
)
STALE_FALLBACK_LABEL = "Source no longer available"


def chips_html(sources: list[dict], heading: str | None = None, stale: bool = False) -> str:
    """
    Build the HTML for the chips shown under an assistant message.

    `sources` is the RETRIEVED chunk set (output of hybrid_search), not
    necessarily what the model cited inline — so the caller passes a heading
    ("Retrieved from") to avoid claiming these are the model's citations
    (issue #2). Chips are deduped by (display_name, section_title, page) so two
    chunks from the same document section render once (issue #3).

    SPEC §22.4 (A73): a PDF chunk shows its stored PAGE NUMBER ("Page N"); DOCX
    chunks show their Word-heading section title. SPEC §22.6 (A77): when `stale`
    is True the stored sources are still rendered, marked plainly as no longer
    available, from the identifying information actually stored, and a plain
    fallback label is used when the record cannot identify a source. Chips are
    never clickable.

    Pure (no Streamlit) so it is unit-testable; `source_chips` renders it.
    """
    if not sources:
        return ""
    seen: set[tuple] = set()
    chips = []
    for s in sources:
        name = s.get("display_name") or ""
        section = s.get("section_title")
        page = s.get("page")
        key = (name, section, page)
        if key in seen:
            continue
        seen.add(key)
        if page is not None:
            tail = f"Page {page}"
        elif section:
            tail = section
        else:
            tail = None
        if name and tail:
            label_text = f"{name} — {tail}"
        elif name:
            label_text = name
        elif tail:
            label_text = tail
        else:
            label_text = STALE_FALLBACK_LABEL
        label = html.escape(label_text)
        chips.append(f'<span class="wa-source-chip wa-source-chip--blue">\u25a4 {label}</span>')
    head = []
    if heading:
        head.append(f'<div class="wa-chip-heading">{html.escape(heading)}</div>')
    if stale:
        head.append(f'<div class="wa-chip-heading">{html.escape(STALE_CITATION_NOTE)}</div>')
    return f'{"".join(head)}<div class="wa-pill-row">{"".join(chips)}</div>'


def source_chips(sources: list[dict], heading: str | None = None, stale: bool = False) -> None:
    """Render `chips_html(...)` (see there for the retrieved-vs-cited, dedupe,
    page-label and stale-citation semantics)."""
    html_str = chips_html(sources, heading, stale=stale)
    if html_str:
        st.html(html_str)


def empty_state(text: str) -> None:
    st.markdown(f'<div class="wa-empty">{html.escape(text)}</div>', unsafe_allow_html=True)
