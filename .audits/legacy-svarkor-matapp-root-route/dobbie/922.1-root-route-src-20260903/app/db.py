"""C2 — session + boot for the web-api module (484.3 T3).

Owns the web layer's DB engine/session and the startup boot():
  * boot() runs init_db(engine) (schema on the motor's shared Base) then
    seed_starter(session) — idempotent. It NEVER passes a Session to init_db
    (that raises sqlalchemy ArgumentError); the engine is the argument.
  * The engine defaults to config.DB_URL — the SAME sqlite file the motor
    writes, so the web layer reads what the motor persists (no second DB, no
    fork). Tests may rebind _engine/_Session to a temp file before boot/requests.

The app's routers (stores/menu) get their sessions from get_db().
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import init_db  # motor shared Base (src, via config R1 sys.path)
from recipes.seed import seed_starter

import app.config as app_config

# Rebinds by tests to a temp engine before boot/requests run.
_engine = None
_Session = None


def _default_engine():
    return create_engine(app_config.DB_URL, connect_args={"check_same_thread": False})


def boot():
    """Idempotent startup: schema on shared Base, then seed the starter shelf.

    If _engine was already bound (e.g. tests pointing at a temp DB), it is
    reused — boot only ever ADDS schema/seed, never replaces an existing bind.
    """
    global _engine, _Session

    if _engine is None:
        _engine = _default_engine()
    if _Session is None:
        _Session = sessionmaker(bind=_engine, autoflush=False)

    engine = _engine
    init_db(engine)           # NOTE: engine, never a Session (ArgumentError otherwise)

    Session = _Session
    session = Session()
    try:
        seed_starter(session)   # idempotent (18 starter recipes)
    finally:
        session.close()
    return engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session (real generator fn).

    FastAPI treats a generator *function* as a yield-dependency; it opens a
    ``with`` around it. We therefore write a real generator, not a function
    that merely returns a context manager (that would trip FastAPI's teardown).
    """
    if _Session is None:
        boot()
    session = _Session()
    try:
        yield session
    finally:
        session.close()
