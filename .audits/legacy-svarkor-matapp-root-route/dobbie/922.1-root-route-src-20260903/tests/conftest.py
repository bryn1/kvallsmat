"""Shared pytest fixtures for the 484.3 web-api module tests.

Sets up sys.path so the app can locate BOTH the motor tree (motor/src) and its
own kvallsmat-web package. Provides a temp sqlite engine schema'd + seeded like
a fresh boot with the N7 fixture data (4 offers via upsert_week + 18 starter
recipes), and rebinds app.db + the store-catalog source (app.config.PLANNER)
so each test runs in isolation WITHOUT touching the app's real DB file.
"""
from __future__ import annotations

import os
import sys
import tempfile

MOTOR_SRC = "/srv/workspace/svarkor-kvallsmat-recept-phase3-phase2/motor/src"
WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # kvallsmat-web/

for p in (MOTOR_SRC, WEB):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy.orm import sessionmaker

import app.config as app_config
import app.db as db_module
from config import PlannerConfig
from database import init_db, make_engine
from offers_db.store import upsert_week
from recipes.seed import seed_starter

WEEK = "2026-W34"

# N7 fixture offers — one per grocer feeding run_motor's week (4 total).
OFFER_FIXTURE = [
    {"grocer_id": "willys", "external_id": "w-1", "name": "Köttfärs 500g",
     "price_cents": 5900, "week_key": WEEK, "valid_from": "2026-08-17",
     "valid_to": "2026-08-23"},
    {"grocer_id": "willys", "external_id": "w-2", "name": "Falukorv 600g",
     "price_cents": 2990, "week_key": WEEK, "valid_from": "2026-08-17",
     "valid_to": "2026-08-23"},
    {"grocer_id": "willys", "external_id": "w-3", "name": "Pannkakssmet",
     "price_cents": 2150, "week_key": WEEK, "valid_from": "2026-08-17",
     "valid_to": "2026-08-23"},
    {"grocer_id": "ica", "external_id": "i-1", "name": "Vitfiskfilé 500g",
     "price_cents": 8900, "week_key": WEEK, "valid_from": "2026-08-17",
     "valid_to": "2026-08-23"},
]

GROCERS = [
    PlannerConfig.grocer("willys", "https://feeds.willys.se/week", chain="willys"),
    PlannerConfig.grocer("ica", "https://feeds.ica.se/week", chain="ica"),
    PlannerConfig.grocer("coop", "https://feeds.coop.se/week", chain="coop"),
]


@pytest.fixture
def booted_db():
    """A temp sqlite, schema'd + seeded + offers ingested, and app rebound to it."""
    tmp = tempfile.mkdtemp(prefix="kvallsmat-4843-")
    db_url = f"sqlite:///{tmp}/test.db"
    engine = make_engine(db_url)
    init_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        seed_starter(session)                 # 18 starter recipes, idempotent
        upsert_week(session, OFFER_FIXTURE, WEEK)
    finally:
        session.close()

    # rebind the app's storage + catalog source to this isolated env
    db_module._engine = engine
    db_module._Session = sessionmaker(bind=engine, autoflush=False)
    app_config.PLANNER = PlannerConfig(grocers=list(GROCERS))

    return {"engine": engine, "db_url": db_url}
