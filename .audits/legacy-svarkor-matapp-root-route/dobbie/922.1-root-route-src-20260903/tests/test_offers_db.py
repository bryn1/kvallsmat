"""RED tests for M4 offers-db (C5). Run: python -m pytest tests/test_offers_db.py"""
import sys, os, importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from database import Base
from offers_db.store import upsert_week, list_offers_in_week, Offer


@pytest.fixture()
def conn():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_upsert_week_writes_rows(conn):
    offer = dict(
        grocer_id="willys", external_id="ext-1", week_key="2026-W34",
        name="Köttfärs 500g", price_cents=5900, unit="st",
        valid_from="2026-08-17", valid_to="2026-08-23",
    )
    n = upsert_week(conn, [offer], "2026-W34")
    assert n == 1
    got = list_offers_in_week(conn, "2026-W34")
    assert len(got) == 1
    assert got[0].grocer_id == "willys"
    assert got[0].price_cents == 5900


def test_upsert_week_idempotent_on_unique_key(conn):
    off = dict(
        grocer_id="willys", external_id="ext-1", week_key="2026-W34",
        name="Köttfärs 500g", price_cents=5900, unit="st",
        valid_from="2026-08-17", valid_to="2026-08-23",
    )
    upsert_week(conn, [off], "2026-W34")
    # same natural key, updated price -> should update, not duplicate
    off["price_cents"] = 4900
    n = upsert_week(conn, [off], "2026-W34")
    assert n == 1
    got = list_offers_in_week(conn, "2026-W34")
    assert len(got) == 1
    assert got[0].price_cents == 4900


def test_week_key_scoped_read(conn):
    base = dict(grocer_id="willys", name="X", price_cents=100, unit="st",
                valid_from="2026-08-17", valid_to="2026-08-23")
    upsert_week(conn, [dict(base, external_id="e1", week_key="2026-W34")], "2026-W34")
    upsert_week(conn, [dict(base, external_id="e2", week_key="2026-W33")], "2026-W33")
    assert len(list_offers_in_week(conn, "2026-W34")) == 1
    assert len(list_offers_in_week(conn, "2026-W33")) == 1


def test_unique_constraint_present(conn):
    insp = inspect(conn.bind)
    uniques = [u["column_names"] for u in insp.get_unique_constraints("offers")]
    assert ["grocer_id", "external_id", "week_key"] in uniques


def test_ow_index_present(conn):
    insp = inspect(conn.bind)
    idx = insp.get_indexes("offers")
    cols = [tuple(i["column_names"]) for i in idx]
    assert ("week_key", "grocer_id") in cols
