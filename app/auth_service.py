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
import time

from fastapi import HTTPException, Request

from app import security
from app import db as dbm
import app.models  # noqa: F401  (register users table before queries)
from app.models.users import User


def current_user_or_401(request: Request) -> User:
    """FastAPI dependency: resolve the session cookie to a User; 401 otherwise.

    The ONE shared auth-gate dependency (MC 1355.16): the profile and menu
    routers already inline this exact gate; the stores router's new
    ``?postal_code=`` preview reuses THIS copy instead of a third inline one
    (T10b §4 — same gate as profile/menu, 401 never 200).
    """
    token = request.cookies.get(security.SESSION_COOKIE)
    user = current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


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


class LoginRateLimiter:
    """Thread-safe per-username failed-login counter with lockout (audit 1188 F2).

    Same scope/idiom as SessionStore: in-memory, module-level, guarded by a
    threading.Lock. After MAX_FAILURES failed logins for a username inside the
    WINDOW seconds, that username is locked out for LOCKOUT seconds — login()
    refuses it (429 at the router) without touching the DB. A successful login
    resets the counter.
    """

    MAX_FAILURES = 5
    WINDOW = 15 * 60  # failure window: 15 minutes
    LOCKOUT = 15 * 60  # lockout duration: 15 minutes

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_locked(self, username: str, now: float | None = None) -> bool:
        """True iff *username* is currently locked out."""
        now = time.monotonic() if now is None else now
        with self._lock:
            until = self._locked_until.get(username)
            if until is None:
                return False
            if now >= until:
                del self._locked_until[username]  # lockout expired
                return False
            return True

    def record_failure(self, username: str, now: float | None = None) -> None:
        """Count one failed login; lock the username at MAX_FAILURES in WINDOW."""
        now = time.monotonic() if now is None else now
        with self._lock:
            recent = [t for t in self._failures.get(username, []) if now - t < self.WINDOW]
            recent.append(now)
            self._failures[username] = recent
            if len(recent) >= self.MAX_FAILURES:
                self._locked_until[username] = now + self.LOCKOUT

    def record_success(self, username: str) -> None:
        """A successful login clears the username's failure counter."""
        with self._lock:
            self._failures.pop(username, None)


# Module-level singleton used by the router; tests may substitute a fresh limiter.
login_limiter = LoginRateLimiter()


class LoginLockedOut(Exception):
    """Raised by login() when the username is locked out (maps to HTTP 429)."""


def authenticate(username: str, password: str) -> User | None:
    """Return the User iff *username* exists and *password* matches its hash.

    Timing-equalized (audit 1188 F3): an unknown username runs the SAME argon2
    verify against a module-level dummy hash (generated at import from a fixed
    dummy string) so the response time matches an existing username's. Target:
    existing vs non-existing within 2x.
    """
    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            security.verify_password(password, security.DUMMY_HASH)
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        return user
    finally:
        session.close()


def login(username: str, password: str) -> str | None:
    """create an opaque session token for *username* iff creds are valid, else None.

    Raises LoginLockedOut when *username* is currently locked out (audit 1188 F2)
    — the router maps that to 429. A failed attempt is counted; a successful one
    resets the username's failure counter.
    """
    if login_limiter.is_locked(username):
        raise LoginLockedOut(username)
    user = authenticate(username, password)
    if user is None:
        login_limiter.record_failure(username)
        return None
    login_limiter.record_success(username)
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


# ---------------------------------------------------------------------------
# Open registration (MC 1355.7, owner-ratified 2026-09-24: open registration)
# ---------------------------------------------------------------------------

MIN_PASSWORD_LENGTH = 8
MAX_USERNAME_LENGTH = 64


class UsernameTaken(Exception):
    """Raised by register() when the username already exists (-> HTTP 409)."""


class WeakPassword(Exception):
    """Raised by register() on a too-short password / bad username (-> 422)."""


def register(username: str, password: str) -> str:
    """Create a new account and return an opaque session token (auto-login).

    Same mechanism as login — the users table, app.security hashing and the
    module SessionStore; no second user mechanism. Raises UsernameTaken when
    the username exists (router -> 409) and WeakPassword on a too-short
    password or an empty/over-long username (router -> 422).
    """
    name = (username or "").strip()
    if not name or len(name) > MAX_USERNAME_LENGTH:
        raise WeakPassword("username must be 1-64 characters")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        if session.query(User).filter_by(username=name).first() is not None:
            raise UsernameTaken(name)
        session.add(User(username=name,
                         password_hash=security.hash_password(password)))
        session.commit()
    finally:
        session.close()
    return sessions.create(name)
