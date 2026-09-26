"""PHASE 2 (T1) db-foundation — USER model on the shared database.Base.

Declares the ``users`` table on the motor-shared Base so ``init_db`` creates it
atomically with every other table (POC fix-2 idiom: import this module BEFORE
init_db runs — see app/db.py boot() and database.py init_db()).

Single concern: account identity for authentication (Phase 3 auth builds on it).
Passwords are stored ONLY as an argon2id hash (never plaintext); the hashing itself
lives in Phase 3, here we only carry the opaque ``password_hash`` string column.

Derived from the root-route POC store_selection.py pattern (single web-layer table
on shared Base) and the OWASP Argon2id requirements in PHASE0-research.md Q3.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from database import Base  # shared Base (import BEFORE init_db — fix-2 idiom)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)  # argon2id hash (Phase 3 writes it)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<User {self.username!r}>"
