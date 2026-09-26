"""RED tests for M1 scheduler (CONTRACT C1).

Run: python3 -m pytest tests/test_scheduler.py -q
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

import pytest

from config import PlannerConfig, GrocerConfig
from scheduler.periodic import choose_week, schedule_run, main


def make_cfg():
    return PlannerConfig(grocers=[
        GrocerConfig(grocer_id="willys", endpoint="https://api.willys.se"),
        GrocerConfig(grocer_id="ica", endpoint="https://api.ica.se", token="t"),
    ])


def test_choose_week_returns_iso_week_of_given_now():
    cfg = make_cfg()
    # 2026-08-20 is a Thursday in ISO week 2026-W34
    got = choose_week(cfg, now=datetime(2026, 8, 20, 12, 0))
    assert got == "2026-W34"


def test_choose_week_formats_week_two_digits():
    cfg = make_cfg()
    # 2026-01-07 -> ISO week 2026-W02 (not W2)
    got = choose_week(cfg, now=datetime(2026, 1, 7, 10, 0))
    assert got == "2026-W02"


def test_schedule_run_returns_all_grocer_ids():
    cfg = make_cfg()
    got = schedule_run(cfg)
    assert got == ["willys", "ica"]


def test_main_runs_full_pipeline_and_writes_offers(tmp_path):
    """End-to-end ingest: main() pulls a feed via fake session, normalizes, upserts
    into a real offers-db. Proves M1+M2+M3→M4 wiring."""
    from offers_db.store import list_offers_in_week

    class FakeResponse:
        status_code = 200
        def __init__(self, payload): self._payload = payload
        def json(self): return self._payload

    class FakeSession:
        def get(self, url, headers=None):
            if "willys" in url:
                return FakeResponse({"offers": [
                    {"external_id": "ext-1", "name": "Köttfärs 500g", "price": 59.00,
                     "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
                ]})
            return FakeResponse({"offers": []})   # ica contributes nothing this run

    cfg = make_cfg()
    db_url = f"sqlite:///{tmp_path/'k.db'}"
    rc = main(cfg=cfg, session=FakeSession(), db_url=db_url, now=datetime(2026, 8, 20))
    assert rc == 0

    from database import make_engine
    from sqlalchemy.orm import sessionmaker
    engine = make_engine(db_url)
    Session = sessionmaker(bind=engine)
    conn = Session()
    offers = list_offers_in_week(conn, "2026-W34")
    assert len(offers) == 1
    assert offers[0].external_id == "ext-1"   # willys chain -> no prefix
    assert offers[0].week_key == "2026-W34"
