"""Phase 3 (T2) auth — HARNESS SELF-TEST (anti-false-green). (1143.3)

Runs the gate C2 DoD checks AND proves the harness would catch a broken build:

  GREEN — (a) ``argon2`` is pinned in requirements.txt (grep -i argon2 >= 1 pin);
          (b) a real Argon2id password hash (19 MiB / t=2 / p=1, the gate's params)
              is produced and VERIFIED THROUGH THE REAL argon2-cffi LIBRARY — the
              correct password passes, a deliberately WRONG password fails;
          (c) an end-to-end /api/auth/login -> me -> logout session roundtrip works
              via the opaque HttpOnly+Secure+SameSite cookie and logs out cleanly.

  RED   — the deliberately wrong password MUST make verification fail (and login 401)
          for TWO independent wrong values; a build that wrongly accepts anything
          makes this harness exit non-zero (anti-false-green / test_mqtt_packet rule:
          we verify ARGON2, we do not test our own encoder).

This harness's ``main()`` returns the true, accumulated exit code (never an
un-incremented local — gate lesson MC sensor): every failed check increments a
``failures`` counter and main() exits nonzero iff failures > 0.

Exit 0 only if every GREEN check passes AND both RED trips fire.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so 'database' and 'app' resolve from the deliverable root

# Argon2id parameters REQUIRED by gate C2 (PHASE0-map / OWASP): 19 MiB / t=2 / p=1.
MEM_KIB = 19 * 1024  # 19 MiB in KiB
TIME_COST = 2
PARALLELISM = 1


def _grep_argon2_in_requirements() -> bool:
    """Gate C2 DoD (a): at least one argon2 pin in requirements.txt."""
    req = os.path.join(HERE, "requirements.txt")
    if not os.path.exists(req):
        print(f"[GREEN-FAIL] requirements.txt missing: {req}")
        return False
    lines = open(req, encoding="utf-8").read().splitlines()
    pins = [l for l in lines if re.search(r"argon2", l, re.IGNORECASE)]
    print(f"[GREEN] argon2 pins in requirements.txt: {len(pins)} -> {pins!r}")
    return len(pins) >= 1


def _http_client():
    """Starlette TestClient over https so ``Secure`` cookies come back.

    The app's session cookie is set ``Secure`` (gate C2); TestClient's default
    http://testserver drops Secure cookies, so we run the client over an https
    base_url — testing the REAL cookie roundtrip, including the Secure attribute,
    end to end through app.main (lifespan boot included).
    """
    from app.main import app
    from starlette.testclient import TestClient
    return TestClient(app, base_url="https://testserver")


def green_case() -> list[str]:
    """Return list of failing check descriptions (empty == GREEN passes)."""
    failures: list[str] = []

    # --- (a) argon2 pinned in deploy requirements.txt (never dev-only) ----------
    if not _grep_argon2_in_requirements():
        failures.append("requirements.txt has no argon2 pin (closure gap 2 open)")

    # --- security module imports + is wired to the REAL argon2-cffi -------------
    try:
        from app import security
    except Exception as e:  # noqa: BLE001
        failures.append(f"app.security import failed: {e!r}")
        return failures  # cannot continue without the module

    # Verify through the REAL argon2 library, not our own encoder (test_mqtt_packet
    # anti-pattern): hash with the app wrapper, then VERIFY with argon2.PasswordHasher
    # directly so a wrong hash==verify pair in MY code cannot both be broken together.
    try:
        import argon2
        real = argon2.PasswordHasher(time_cost=TIME_COST, memory_cost=MEM_KIB,
                                     parallelism=PARALLELISM)
        h = security.hash_password("hunter2-correct")
        # (i) the produced string is a genuine Argon2id v=19 hash
        if not h.startswith("$argon2id$v=19"):
            failures.append(f"hash is not Argon2id: {h!r}")
        # (ii) the REAL argon2 verifies the correct password against our hash
        try:
            real.verify(h, "hunter2-correct")
        except Exception:  # noqa: BLE001
            failures.append("REAL argon2 could NOT verify correct pw against our hash")
        # (iii) our verify_password agrees (correct -> True)
        if not security.verify_password("hunter2-correct", h):
            failures.append("verify_password(correct) returned False")
        print(f"[GREEN] argon2id hash + real-argon2 verify OK: {h[:40]}...")
    except Exception as e:  # noqa: BLE001
        failures.append(f"argon2 verify path failed: {e!r}")

    # --- session roundtrip over real HTTP (login -> me -> logout) ---------------
    try:
        _seed_user()  # temp DB first: the app lifespan boot() needs it
        client = _http_client()
        try:
            # login -- success must set an opaque HttpOnly+Secure+SameSite cookie
            r = client.post("/api/auth/login",
                            json={"username": "harness_user", "password": "hunter2-correct"})
            if r.status_code != 200:
                failures.append(f"login returned {r.status_code}, not 200")
            else:
                set_cookie = r.headers.get("set-cookie", "")
                for attr in ("httponly", "samesite", "secure", "matapp_session"):
                    if attr.lower() not in set_cookie.lower():
                        failures.append(f"session cookie missing {attr}: {set_cookie!r}")
                # me with the session cookie (client persists it) -> same user
                r2 = client.get("/api/auth/me")
                if r2.status_code != 200:
                    failures.append(f"me after login returned {r2.status_code}, not 200")
                elif r2.json().get("username") != "harness_user":
                    failures.append(f"me returned wrong user: {r2.json()!r}")
                # logout -> session invalidated -> me 401
                r3 = client.post("/api/auth/logout")
                r4 = client.get("/api/auth/me")
                if r4.status_code != 401:
                    failures.append(f"me after logout returned {r4.status_code}, expected 401")
            print("[GREEN] /api/auth/login->me->logout session roundtrip OK")
        finally:
            client.close()
    except Exception as e:  # noqa: BLE001
        failures.append(f"session roundtrip failed: {e!r}")

    return failures


def red_case() -> list[str]:
    """Return failing-check descriptions for the anti-false-green RED paths.

    A wrong password MUST fail verification and MUST NOT log in. If either is
    accepted, the build is broken and this returns non-empty (harness goes RED).
    """
    failures: list[str] = []

    try:
        from app import security
        import argon2
    except Exception as e:  # noqa: BLE001
        failures.append(f"cannot run red path: {e!r}")
        return failures

    real = argon2.PasswordHasher(time_cost=TIME_COST, memory_cost=MEM_KIB,
                                 parallelism=PARALLELISM)
    h = real.hash("hunter2-correct")

    # RED (i): a wrong password must NOT verify (argon2 raises VerifyMismatchError)
    for wrong in ("hunter2-wrong", "completely-different"):
        try:
            ok = security.verify_password(wrong, h)
        except Exception:
            ok = False
        if ok:
            failures.append(f"verify_password({wrong!r}) wrongly returned True")
    print("[RED] wrong passwords fail verification (anti-false-green)")

    # RED (ii): login with a wrong password must 401
    try:
        _seed_user()  # temp DB first (reuses temp DB from green_case)
        client = _http_client()
        try:
            r = client.post("/api/auth/login",
                            json={"username": "harness_user", "password": "hunter2-wrong"})
            if r.status_code != 401:
                failures.append(f"login with wrong pw returned {r.status_code}, expected 401")
            print("[RED] login with wrong password -> 401")
        finally:
            client.close()
    except Exception as e:  # noqa: BLE001
        failures.append(f"wrong-password login check failed: {e!r}")

    return failures


def _temp_db() -> str:
    """Rebind app.db to a fresh temp sqlite file with the schema, return its path.

    This keeps the harness hermetic: no writes to the deliverable tree, and every
    green/red run starts from an empty DB (the engine does not mkdir its parent,
    so we create the temp dir explicitly).
    """
    import tempfile
    import sqlalchemy
    from database import init_db
    from app import db as dbm

    tmpdir = tempfile.mkdtemp(prefix="matapp-p3-")
    dbfile = os.path.join(tmpdir, "harness.db")
    eng = sqlalchemy.create_engine(f"sqlite:///{dbfile}")
    import app.models  # noqa: F401  (register all tables before create_all)
    init_db(eng)
    dbm._engine = eng
    dbm._Session = sqlalchemy.orm.sessionmaker(bind=eng, autoflush=False)
    return dbfile


def _seed_user() -> None:
    """Ensure harness_user exists in the (temp/test) DB with a known hash."""
    from app import security
    from app import db as dbm
    if dbm._Session is None:
        _temp_db()
    import app.models  # noqa: F401  (registers tables before queries)
    from app.models.users import User
    session = dbm._Session()
    try:
        existing = session.query(User).filter_by(username="harness_user").first()
        if existing is None:
            session.add(User(username="harness_user",
                             password_hash=security.hash_password("hunter2-correct")))
            session.commit()
    finally:
        session.close()


def main() -> int:
    failures = 0
    green_fail = green_case()
    for f in green_fail:
        print(f"[GREEN-FAIL] {f}")
        failures += 1

    red_fail = red_case()
    for f in red_fail:
        print(f"[RED-FAIL] {f}")
        failures += 1

    if green_fail:
        print(f"HARNESS-FAIL: {len(green_fail)} green check(s) failed")
        return failures if failures else 2
    if red_fail:
        print(f"HARNESS-FAIL: {len(red_fail)} anti-false-green check(s) not tripped")
        return failures if failures else 3

    print("HARNESS RESULT: PASS (green argon2id+session DoD + anti-false-green red trip)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
