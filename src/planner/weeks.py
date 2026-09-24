"""ISO week-key math — the ONE shared week-math helper (MC 1355.5, audit P2-4).

Both week-key consumers (``src/planner/menu.py`` and ``app/optimizer/optimizer.py``)
previously carried their own ``_week_to_monday`` copy. The two copies drifted into the
exact bug-pair the audit flagged as P2-3 (BUG-1: ``OverflowError`` on ``9999-W99``;
BUG-2: silent extrapolation of ``2026-W54`` into 2027). This module owns the math once:

  * ``week_to_monday`` validates the key as a REAL ISO week (via
    ``date.fromisocalendar``, which rejects week 0, week 54, and out-of-range years)
    and raises ``ValueError`` for anything malformed — never ``OverflowError``,
    never a silent extrapolation.
  * ``current_week_key`` derives the display key for the running week.

Single concern: ISO week-key parsing/derivation. No planner or DB logic here.
"""
from __future__ import annotations

from datetime import date, datetime


def week_to_monday(week_key: str) -> date:
    """Resolve an ISO-8601 week key like '2026-W34' to that week's Monday.

    Raises ValueError for malformed keys AND for keys that are not a real week
    (``2026-W00``, ``2026-W54``, ``9999-W99``, ``0000-W01``) — the boundary fix
    for audit BUG-1/BUG-2.
    """
    if not isinstance(week_key, str) or "-" not in week_key:
        raise ValueError(f"week_key must look like '2026-W34', got {week_key!r}")
    year_str, _, week_str = week_key.partition("-")
    try:
        year, wk = int(year_str), int(week_str.lstrip("Ww"))
    except ValueError:
        raise ValueError(f"bad week_key {week_key!r}") from None
    try:
        # ISO 8601: week 1 is the week containing the first Thursday of the year.
        # fromisocalendar validates the week against the year's real week count.
        return date.fromisocalendar(year, wk, 1)
    except ValueError:
        raise ValueError(f"week_key is not a real ISO week: {week_key!r}") from None


def current_week_key(now: datetime | None = None) -> str:
    """Display week key 'YYYY-Www' of the running (or given) moment."""
    iso = (now or datetime.now()).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"
