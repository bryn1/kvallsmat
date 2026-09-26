"""M2 fetcher.adapters._common — shared helpers for the grocer adapters.

Kept in its own module so the per-grocer adapters and the dispatch
``__init__`` can both import it without a circular import.
"""
from __future__ import annotations

from datetime import date


def week_start(week_key: str) -> str:
    """ISO week key "YYYY-Www" -> Monday date "YYYY-MM-DD" ('' on bad input)."""
    try:
        year, week = week_key.split("-W")
        return date.fromisocalendar(int(year), int(week), 1).isoformat()
    except (ValueError, AttributeError):
        return ""


def get_text(session, url: str, headers: dict | None = None) -> str | None:
    """GET a page as text; None on non-200 or any network/decode error."""
    try:
        resp = session.get(url, headers=headers or {})
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def get_json(session, url: str, headers: dict | None = None):
    """GET a page as parsed JSON; None on non-200, network error or bad JSON.

    Shared by the offer adapters AND the src/locator store locators (T10b §2:
    the locator package imports the shared helpers, never duplicates them).
    """
    import json

    raw = get_text(session, url, headers)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
