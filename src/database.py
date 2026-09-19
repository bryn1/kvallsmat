"""Shared SQLAlchemy setup for the Kwallsmat backend DB-lager (M4 offers-db, M6 recipe-db).

Fleet-proven Hotell idiom: one declarative Base, a synchronous SQLite engine, and a
session factory. Callers build a session and pass it as the contract's ``conn``
argument (REV6 contract wording). These modules are pure persistence — no web/async —
so the sync sqlite driver is sufficient here.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def make_engine(url="sqlite:///kvallsmat.db", **kwargs):
    """Create a sqlite engine. In-memory used by tests; file path used in production."""
    connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args, **kwargs)


def get_session(engine=None, url="sqlite:///kvallsmat.db"):
    """Return a fresh Session bound to *engine* (created from *url* if not given)."""
    if engine is None:
        engine = make_engine(url)
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(engine=None):
    """Create all tables. Safe to call on every boot (idempotent)."""
    if engine is None:
        engine = make_engine()
    Base.metadata.create_all(bind=engine)
    return engine
