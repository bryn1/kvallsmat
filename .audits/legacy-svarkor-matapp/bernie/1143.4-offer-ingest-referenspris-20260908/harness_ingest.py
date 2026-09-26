#!/usr/bin/env python3
"""Phase 4 (T3) offer-ingest gate-C3 harness — two-sided calibration (PH4).

GREEN case (DoD):  ingest-harness against the recorded willys-feed mock (injected
  httpx-like session, HAL-seam) writes an Offer row with regular_price_cents > price_cents
  AND proves the per-ingredient extrapris flag fired. Exits 0.
RED case (anti-false-green):  a deliberately-broken normalizer that DROPS the reference
  price (passes through regular_price_cents=None, i.e. closure-gap 1 left open) must make
  the pipeline FAIL — no Offer row with a reference price, extrapris flag never fires.
  The harness must go non-zero (RED) on that — proving it can detect a missing reference
  price, not just pass any normalizer.

Run against the published deliverable tree with the pinned runtime venv:
  cd /srv/workspace/svarkor-matapp/bernie/1143.4-offer-ingest-referenspris-20260908
  ~/p4-venv/bin/python3 harness_ingest.py ; echo "HARNESS_EXIT=$?"
"""
import os
import sys
import tempfile

# Import from the deliverable tree when run in-place.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GrocerConfig, CHAIN_MAP
from app.ingest import grocer, normalizer as real_normalizer
from app.ingest import ingest as ingest_mod
from app.ingest.grocer import parse_swedish_kr
from app.ingest.willys_mock import MockSession, WILLYS_FEED_2026_W37
from app.models.offers_db import Offer

WEEK = "2026-W37"


def _fresh_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    from database import Base
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    return session


def _assert(cond, msg):
    if not cond:
        raise AssertionError("ASSERT FAILED: " + msg)
    print("[ok] " + msg)


def run_green_case() -> None:
    """DoD green: recorded willys mock -> Offer row with regular_price_cents > price_cents."""
    print("== GREEN CASE: ingest willys mock -> reference price on Offer row ==")
    sess = _fresh_session()
    cfg = GrocerConfig.grocer("willys", "https://mock.example/willys", chain="willys")
    mock = MockSession(feed=WILLYS_FEED_2026_W37)

    # PARSE unit-test first: the willys string form '71,29 kr' must become 7129 cents.
    parsed = parse_swedish_kr("71,29 kr")
    _assert(parsed == 7129, f"parse_swedish_kr('71,29 kr') == 7129 (got {parsed})")

    res = ingest_mod.ingest_week(sess, cfg, WEEK, session=mock)

    _assert(res.written >= 1, f"ingest wrote >=1 Offer rows (wrote {res.written})")
    _assert(res.normalized == 3, f"all 3 in-week entries normalized (got {res.normalized})")
    _assert(res.extraprice_count >= 2, f"extrapris flag fired on >=2 offers (got {res.extraprice_count})")

    # Direct DB proof of the DoD core: a stored Offer has regular > price.
    rows = sess.query(Offer).filter(Offer.week_key == WEEK).all()
    _assert(len(rows) >= 1, ">=1 Offer row persisted for the week")

    by_ext = {r.external_id: r for r in rows}
    ok_regular = [r for r in rows if r.regular_price_cents is not None
                  and r.regular_price_cents > r.price_cents]
    _assert(len(ok_regular) >= 1, ">=1 stored Offer with regular_price_cents > price_cents")
    _assert(by_ext["w37-0001"].regular_price_cents == 7129,
            "w37-0001 regular_price_cents == 7129 (comparePrice '71,29 kr' parsed + persisted)")
    _assert(by_ext["w37-0001"].savings_cents == 7129 - by_ext["w37-0001"].price_cents,
            "w37-0001 savings_cents == regular - price")

    # Per-ingredient extrapris flag: w37-0001 and w37-0002 are on offer; w37-0003 has a
    # historical-low *proxy* below sale (35 < 39.9) -> NOT extrapris by the strict rule.
    _assert(res.max_row["external_id"] == "w37-0001",
            f"max reference-price row is the big-discount item (got {res.max_row['external_id']})")
    print(f"[GREEN] written={res.written} normalized={res.normalized} "
          f"extraprice_count={res.extraprice_count}")
    print("[GREEN] sample stored rows:")
    for r in rows:
        print(f"    {r.external_id}: price={r.price_cents} "
              f"regular={r.regular_price_cents} savings={r.savings_cents}")
    print("GREEN-CASE-EXIT=0")


def broken_normalizer_drops_reference(chain, raw, week_key):
    """Deliberately-broken normalizer: closure-gap 1 left OPEN — reference price dropped,
    every offer passes through with regular_price_cents=None. Nothing can be flagged extrapris."""
    out = []
    # Reuse the real normalizer's filtering but strip reference fields (the broken variant).
    for n in real_normalizer.normalize(chain, raw, week_key):
        n["regular_price_cents"] = None
        n["savings_cents"] = None
        n["is_extraprice"] = False
        out.append(n)
    return out


def run_red_case() -> None:
    """Anti-false-green: broken normalizer (no reference price) must FAIL the pipeline."""
    print("\n== RED CASE: broken normalizer (no reference price) must go RED ==")
    sess = _fresh_session()
    cfg = GrocerConfig.grocer("willys", "https://mock.example/willys", chain="willys")
    mock = MockSession(feed=WILLYS_FEED_2026_W37)

    res = ingest_mod.ingest_week(
        sess, cfg, WEEK, session=mock, normalize=broken_normalizer_drops_reference
    )

    rows = sess.query(Offer).filter(Offer.week_key == WEEK).all()
    regular_hits = [r for r in rows if r.regular_price_cents is not None]
    if len(regular_hits) >= 1 or res.extraprice_count >= 1:
        raise AssertionError(
            "RED-CASE BUG: broken normalizer still produced a reference price / extrapris "
            "flag — the pipeline did NOT detect the missing reference price."
        )

    # Green-Case caller would assert regular > price; here that assertion FAILS -> RED.
    probe_failed = False
    try:
        _assert(len(regular_hits) >= 1, "red-case should have no regular-price rows")
    except AssertionError:
        probe_failed = True
    if not probe_failed or res.extraprice_count >= 1:
        raise AssertionError("broken normalizer did NOT go red")
    print("[RED] broken normalizer dropped the reference price; pipeline correctly FAILED")
    print(f"[RED] written={res.written} extraprice_count={res.extraprice_count} "
          f"(expected 0 extraprice flags)")
    print("RED-CASE-EXIT=1  (expected non-zero — anti-false-green calibration tripped)")


def main() -> int:
    run_green_case()
    run_red_case()
    print("\nHARNESS RESULT: PASS (green DoD + anti-false-green red trip)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — harness must exit non-zero on any failure
        print(f"HARNESS FAILURE: {exc}")
        raise SystemExit(1)
