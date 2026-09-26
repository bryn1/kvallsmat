"""Shared SQLAlchemy Base for the matapp framtidsvision backend DB-lager (Phase 2 db-foundation).

Fleet-proven Hotell/Kvällsmats idiom: ONE declarative Base, a synchronous SQLite engine,
and a session factory. All tables — users, profile, stores, recipes, offers — are declared
on THIS Base, so ``init_db`` creates the whole schema atomically in one ``create_all``.

Pure persistence — no web/async — so the sync sqlite driver is sufficient.

Phase 2 (T1) requirement (PHASE0.md §P Phase 2): the ``users`` and ``profile`` tables are
declared on this shared ``database.Base``, and every model module is imported BEFORE
``init_db`` runs (POC fix-2 idiom, see app/db.py boot()), so $create_all sees every table.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def make_engine(url: str | None = None, **kwargs):
    """Create a sqlite engine. In-memory used by tests; file path used in production."""
    connect_args = {"check_same_thread": False}
    if url is None:
        # Default to a project-local data file, mirrors the root-route app.
        here = os.path.dirname(os.path.abspath(__file__))
        url = os.environ.get("MATAPP_DB_URL", f"sqlite:///{here}/.data/matapp.db")
    return create_engine(url, connect_args=connect_args, **kwargs)


def get_session(engine=None, url: str | None = None):
    """Return a fresh Session bound to *engine* (created from *url* if not given)."""
    if engine is None:
        engine = make_engine(url)
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(engine=None):
    """Create all tables on the shared Base. Safe to call on every boot (idempotent).

    Importing every model module BEFORE this runs is what registers the tables on
    ``Base.metadata`` (fix-2 idiom). app/db.py does that; standalone callers must too.
    """
    if engine is None:
        engine = make_engine()
    Base.metadata.create_all(bind=engine)
    return engine
