"""
credentials.py — API key expiry status (SPEC.md §14.5).

Pure computation module. No Streamlit import (SPEC.md §8 rule 2). This module
computes; app.py renders.

api_key_status() never raises — it is called on every render and an exception
here would take down every page. A malformed/unset/empty variable returns
state "unknown".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

# How far before expiry the orange pre-expiry warning starts (SPEC §14.5).
KEY_EXPIRY_WARNING_DAYS = 14

_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class KeyStatus:
    state: str  # "ok" | "expiring" | "expired" | "unknown"
    expires_on: str | None  # the configured YYYY-MM-DD, or None when unknown
    days_remaining: int | None  # None when unknown


def api_key_status() -> KeyStatus:
    """
    State per SPEC §14.5:
      - expired  when days_remaining < 0
      - expiring when 0 <= days_remaining <= KEY_EXPIRY_WARNING_DAYS
      - ok       above that
      - unknown  when the variable is unset, empty, or unparseable

    Days are compared against today's UTC date; the key is valid through the
    end of the named day (days_remaining == 0 means "expires today, still
    usable").
    """
    raw = os.environ.get("OPENAI_API_KEY_EXPIRES_ON", "").strip()
    if not raw:
        return KeyStatus("unknown", None, None)

    try:
        expires = datetime.strptime(raw, _DATE_FORMAT).date()
    except ValueError:
        return KeyStatus("unknown", None, None)

    today_utc = datetime.now(timezone.utc).date()
    days_remaining = (expires - today_utc).days
    if days_remaining < 0:
        state = "expired"
    elif days_remaining <= KEY_EXPIRY_WARNING_DAYS:
        state = "expiring"
    else:
        state = "ok"
    return KeyStatus(state, raw, days_remaining)