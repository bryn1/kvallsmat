"""tests.test_auth_fixround2 — F2 rate-limit/lockout + F3 timing-equalizer (audit 1188).

F2: after MAX_FAILURES failed logins for a username inside WINDOW, login() raises
LoginLockedOut (router -> 429); a successful login resets the counter.
F3: authenticate() against a non-existent username runs the same argon2 verify as
an existing one (dummy hash), so the timing difference stays under 2x.
"""
from __future__ import annotations

import time

from app import auth_service, security


def _mkuser(username: str, password: str) -> None:
    """Insert a user row directly (temp-DB engine is already booted by client())."""
    from app import db as dbm
    from app.models.users import User

    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        existing = session.query(User).filter_by(username=username).first()
        if existing is not None:
            return  # idempotent: user already inserted in this temp DB
        session.add(User(username=username,
                         password_hash=security.hash_password(password)))
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------- F2 lockout

def test_lockout_triggers_after_max_failures(fresh_auth):
    limiter = fresh_auth.login_limiter
    for _ in range(limiter.MAX_FAILURES):
        assert fresh_auth.login("ghost", "wrong") is None
    assert limiter.is_locked("ghost") is True


def test_lockout_returns_429_via_router(client, fresh_auth):
    limiter = fresh_auth.login_limiter
    for _ in range(limiter.MAX_FAILURES):
        r = client.post("/api/auth/login",
                        json={"username": "ghost", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/login",
                    json={"username": "ghost", "password": "wrong"})
    assert r.status_code == 429
    assert "too many failed logins" in r.json()["detail"]


def test_lockout_refuses_even_correct_password(client, fresh_auth):
    _mkuser("lockme", "right-pass")
    limiter = fresh_auth.login_limiter
    for _ in range(limiter.MAX_FAILURES):
        assert fresh_auth.login("lockme", "wrong") is None
    # Locked: even the CORRECT password is refused (429, not a session).
    r = client.post("/api/auth/login",
                    json={"username": "lockme", "password": "right-pass"})
    assert r.status_code == 429


def test_successful_login_resets_counter(client, fresh_auth):
    _mkuser("resetter", "right-pass")
    limiter = fresh_auth.login_limiter
    # MAX_FAILURES - 1 failures: not yet locked...
    for _ in range(limiter.MAX_FAILURES - 1):
        assert fresh_auth.login("resetter", "wrong") is None
    assert limiter.is_locked("resetter") is False
    # ...one success resets the counter, so another full run of failures
    # is needed before lockout.
    assert fresh_auth.login("resetter", "right-pass") is not None
    for _ in range(limiter.MAX_FAILURES - 1):
        assert fresh_auth.login("resetter", "wrong") is None
    assert limiter.is_locked("resetter") is False  # reset happened


def test_lockout_expires_after_window(fresh_auth):
    limiter = fresh_auth.login_limiter
    for _ in range(limiter.MAX_FAILURES):
        limiter.record_failure("ghost", now=0.0)
    assert limiter.is_locked("ghost", now=limiter.LOCKOUT - 1) is True
    assert limiter.is_locked("ghost", now=limiter.LOCKOUT + 1) is False


def test_failures_outside_window_do_not_count(fresh_auth):
    limiter = fresh_auth.login_limiter
    old = -(limiter.WINDOW + 1.0)
    for _ in range(limiter.MAX_FAILURES - 1):
        limiter.record_failure("ghost", now=old)
    limiter.record_failure("ghost")  # now: only ONE failure inside the window
    assert limiter.is_locked("ghost") is False


def test_lockout_is_per_username(fresh_auth):
    limiter = fresh_auth.login_limiter
    for _ in range(limiter.MAX_FAILURES):
        limiter.record_failure("user-a")
    assert limiter.is_locked("user-a") is True
    assert limiter.is_locked("user-b") is False


# ---------------------------------------------------------------- F3 timing

def test_timing_existing_vs_nonexisting_under_2x(fresh_auth):
    _mkuser("timinguser", "timing-pass")
    rounds = 5
    times_existing: list[float] = []
    times_ghost: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        assert fresh_auth.authenticate("timinguser", "timing-pass") is not None
        times_existing.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        assert fresh_auth.authenticate("no-such-user", "timing-pass") is None
        times_ghost.append(time.perf_counter() - t0)
    med_existing = sorted(times_existing)[rounds // 2]
    med_ghost = sorted(times_ghost)[rounds // 2]
    ratio = max(med_existing, med_ghost) / min(med_existing, med_ghost)
    # The DoD target: existing vs non-existing within 2x.
    assert ratio < 2.0, (
        f"timing oracle: existing={med_existing*1000:.1f}ms "
        f"ghost={med_ghost*1000:.1f}ms ratio={ratio:.2f}x"
    )


def test_dummy_hash_is_real_argon2id(security_module=None):
    """The F3 dummy hash is a genuine argon2id PHC string the verifier accepts."""
    assert security.DUMMY_HASH.startswith("$argon2id$")
    assert security.verify_password(security.DUMMY_PASSWORD, security.DUMMY_HASH) is True
    assert security.verify_password("not-the-dummy", security.DUMMY_HASH) is False
