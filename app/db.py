"""app.db — session + boot for the matapp web-api (Phase 2 T1 db-foundation).

Owns the web layer's DB engine/session and the startup boot():

  * boot() runs init_db(engine) — schema on the shared Base — creating every table
    (users, profile, offers, ...) atomically, then returns the engine. It NEVER
    passes a Session to init_db (that raises sqlalchemy ArgumentError).
  * FIX-2 idiom (phase-0 gate, POC app/main.py): every model module is imported at
    MODULE scope HERE, so all tables (users/profile/offers/etc.) are registered on
    ``Base.metadata`` BEFORE any init_db/create_all can be called — regardless of
    how app.db is imported. No caller is left to remember to import the models.
  * The engine defaults to database.make_engine() — the SAME sqlite file the rest
    of the app reads. Tests may rebind _engine/_Session to a temp file before
    boot/requests.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base, init_db  # shared Base + schema creation

# FIX-2 idiom: import every model module BEFORE boot/init_db so their tables are
# registered on Base. This import registers users/profile/offers on the shared Base.
import app.models  # noqa: F401,E402  (registers users, profile, offers tables)


# Rebinds by tests to a temp engine before boot/requests run.
_engine = None
_Session = None


def _default_engine():
    from database import make_engine
    return make_engine()


def db_url() -> str:
    """The DB URL the web layer is bound to (MC 1355.5 boot-ingest seam).

    Returns the bound engine's URL when one is set (tests rebind to a temp file),
    else the same default ``database.make_engine`` resolves — ONE url source, so
    the boot-time ingest writes to the very DB the app reads.
    """
    if _engine is not None:
        return str(_engine.url)
    from database import default_url
    return default_url()


def boot():
    """Idempotent startup: create the whole schema on the shared Base.

    If _engine was already bound (e.g. tests pointing at a temp DB), it is reused
    — boot only ever ADDS schema, never replaces an existing bind.
    """
    global _engine, _Session

    if _engine is None:
        _engine = _default_engine()
    if _Session is None:
        _Session = sessionmaker(bind=_engine, autoflush=False)

    engine = _engine
    init_db(engine)  # NOTE: engine, never a Session (ArgumentError otherwise)
    return engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session (real generator fn).

    FastAPI treats a generator *function* as a yield-dependency. A real generator,
    not a function returning a context manager (that trips FastAPI's teardown).
    """
    if _Session is None:
        boot()
    session = _Session()
    try:
        yield session
    finally:
        session.close()
