"""app.ingest.ingest — orchestrate the offer-ingest line end-to-end (Phase 4 T3).

ingest_week(conn, grocer_cfg, week_key, session=None) -> IngestResult
  ONE call runs the full pipeline for one grocer/week:
    fetcher (pull_grocer, injected-session mock or real httpx)
      -> normalizer (RawOffer -> NormalizedOffer w/ reference price + extrapris flag)
      -> persist (upsert_week onto the shared offers table, writing regular_price_cents /
                   savings_cents — closure-gap 1).

This is the module the PHASE 4 gate-C3 harness drives: it must write an Offer row with
regular_price_cents > price_cents from a recorded willys-feed mock, prove the extrapris
flag fired, and go RED when the normalizer drops the reference price.

Writes to the SAME offers table Phase 2 declared (app.models.offers_db.Offer on shared
database.Base). upsert is idempotent on (grocer_id, external_id, week_key) — re-running a
week updates rows instead of duplicating (REV6 CONTRACT C5 / N2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ingest import grocer, normalizer


@dataclass
class IngestResult:
    grocer_id: str
    week_key: str
    pulled_entries: int      # raw entries fetched
    normalized: int          # entries that passed the normalizer
    written: int             # Offer rows upserted to the DB
    extraprice_count: int    # normalized offers flagged is_extraprice
    max_row: dict | None     # the written Offer row with the largest regular price (for harness)


def _upsert_offer(conn: Session, row: dict) -> None:
    """Idempotent write of one normalized offer row onto the shared offers table."""
    from app.models.offers_db import Offer

    key = {
        "grocer_id": row["grocer_id"],
        "external_id": row["external_id"],
        "week_key": row["week_key"],
    }
    existing = conn.query(Offer).filter_by(**key).first()
    payload = {
        "name": row["name"],
        "price_cents": row["price"],
        "regular_price_cents": row.get("regular_price_cents"),
        "savings_cents": row.get("savings_cents"),
        "unit": row.get("unit"),
        "valid_from": row.get("valid_from"),
        "valid_to": row.get("valid_to"),
    }
    if existing is None:
        conn.add(Offer(**key, **payload))
    else:
        for k, v in payload.items():
            setattr(existing, k, v)


def ingest_week(
    conn: Session,
    grocer_cfg,
    week_key: str,
    session: Any = None,
    normalize=normalizer.normalize,
) -> IngestResult:
    """Run pull -> normalize -> persist for one grocer/week. ``normalize`` is injectable
    so the harness can hand in a deliberately-broken normalizer (no reference price) to
    prove the pipeline detects the missing reference price (anti-false-green)."""
    raw = grocer.pull_grocer(grocer_cfg, week_key, session=session)
    normalized_rows = normalize(grocer_cfg.chain, raw, week_key)

    written = 0
    extraprice_count = 0
    max_row: dict | None = None
    for row in normalized_rows:
        _upsert_offer(conn, row)
        written += 1
        if row.get("is_extraprice"):
            extraprice_count += 1
        if row.get("regular_price_cents") is not None:
            if max_row is None or row["regular_price_cents"] > max_row["regular_price_cents"]:
                max_row = dict(row)
    conn.commit()

    return IngestResult(
        grocer_id=grocer_cfg.grocer_id,
        week_key=week_key,
        pulled_entries=len(raw.get("entries") or []),
        normalized=len(normalized_rows),
        written=written,
        extraprice_count=extraprice_count,
        max_row=max_row,
    )
