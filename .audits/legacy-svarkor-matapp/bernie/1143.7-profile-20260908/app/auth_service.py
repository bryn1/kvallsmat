"""app.auth_service — server-side opaque session store + login/logout/me logic (Phase 3 T2 auth).

The session-cookie value is UNPREDICTABLE and OPAQUE (``secrets.token_urlsafe``), and
holds no user data; the token -> username mapping lives server-side in a SessionStore.
This is the auth-seam PHASE0-map §A2 requires: "server-sidig session (opak cookie) —
ingen egen krypto, bibliotek". We store only the token and the owning username.

Single concern: session lifecycle + identity resolution against the users table.
Password hashing stays in app/security.py; HTTP wire-up is in app/routers/auth.py.

NOTE (Phase 3 scope): sessions are held in-memory for this phase — restarting the
process drops them. That is acceptable for the C2 harness; persisting sessions to the
DB is deferred (Phase 5 / api-lager can back this store with a table if required).
"""
from __future__ import annotations

import secrets
import threading

from app import security
from app import db as dbm
import app.models  # noqa: F401  (register users table before queries)
from app.models.users import User


class SessionStore:
    """Thread-safe mapping of opaque session token -> username.

    ``token`` is server-generated with high entropy (unpredictable/opaque) and is
    the ONLY thing stored in the cookie.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._lock = threading.Lock()

    def create(self, username: str) -> str:
        """Issue a new opaque token bound to *username*."""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = username
        return token

    def get(self, token: str) -> str | None:
        with self._lock:
            return self._sessions.get(token)

    def delete(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)


# Module-level singleton used by the router; tests may substitute a fresh store.
sessions = SessionStore()


def authenticate(username: str, password: str) -> User | None:
    """Return the User iff *username* exists and *password* matches its hash."""
    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        return user
    finally:
        session.close()


def login(username: str, password: str) -> str | None:
    """create an opaque session token for *username* iff creds are valid, else None."""
    user = authenticate(username, password)
    if user is None:
        return None
    return sessions.create(user.username)


def current_user(token: str | None) -> User | None:
    """Resolve an opaque session token back to its User (None if invalid/expired)."""
    if not token:
        return None
    username = sessions.get(token)
    if username is None:
        return None
    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        return session.query(User).filter_by(username=username).first()
    finally:
        session.close()


def logout(token: str | None) -> None:
    """Invalidate a session token (idempotent)."""
    if token:
        sessions.delete(token)
