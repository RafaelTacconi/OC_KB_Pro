"""
ui/export.py — Markdown export of a Chat (SPEC §16.2).

`chat_to_markdown` is a PURE builder (no Streamlit); `ui/chat_view.py` renders
the download button. For each turn it emits the question, the answer, the
retrieved sources, the model (display name + .env slug), and the timestamp.

PRIVACY (conscious decision, SPEC §16.2 / memory.md): an export takes internal
procedure content out of the app as an UNCONTROLLED file. Acceptable for this
PoC on the owner's own machine; must be revisited before other people use it.
"""

from __future__ import annotations

import json
from datetime import datetime

from models.registry import get_model_spec, provider_model_name
from ui.cards import format_local_time


def _model_label(model_id: str) -> str:
    try:
        spec = get_model_spec(model_id)
    except ValueError:
        return model_id
    slug = provider_model_name(model_id)
    return f"{spec.display_name} ({slug})" if slug else spec.display_name


def _sources(cited) -> list[str]:
    """Normalise a message's cited_sources (JSON string or list) to display
    strings, deduped by (display_name, section_title)."""
    if not cited:
        return []
    try:
        data = json.loads(cited) if isinstance(cited, str) else cited
    except (TypeError, ValueError):
        return []
    seen: set[tuple] = set()
    out: list[str] = []
    for s in data:
        name = s.get("display_name", "Source")
        section = s.get("section_title")
        key = (name, section)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{name} — {section}" if section else name)
    return out


def chat_to_markdown(title: str, messages: list[dict]) -> str:
    """Render one Chat's messages (DB rows, oldest first) to Markdown."""
    lines: list[str] = [f"# {title}", ""]
    for m in messages:
        role = "Question" if m.get("role") == "user" else "Answer"
        ts = format_local_time(m.get("created_at", ""))
        lines.append(f"## {role}" + (f" — {ts}" if ts else ""))
        lines.append("")
        lines.append(m.get("content", "") or "")
        lines.append("")
        if m.get("role") == "assistant":
            if m.get("model_id"):
                lines.append(f"**Model:** {_model_label(m['model_id'])}")
                lines.append("")
            sources = _sources(m.get("cited_sources"))
            if sources:
                lines.append("**Retrieved from:**")
                lines.append("")
                for s in sources:
                    lines.append(f"- {s}")
                lines.append("")
    lines.append(f"_Exported {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    return "\n".join(lines).rstrip() + "\n"