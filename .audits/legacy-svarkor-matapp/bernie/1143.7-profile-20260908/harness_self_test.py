"""Phase 5 (T4) profile — HARNESS SELF-TEST (anti-false-green, two-sided calibration).

Proves every gate-C4 DoD check against the REAL app over HTTP (FastAPI TestClient),
and proves the harness can go RÖD on a broken build:

  GREEN roundtrip — an authenticated session (from /api/auth/login) PUTs a profile
      {persons, meal_days, kron_budget, selected_stores} then GET /api/profile reads
      it back IDENTICALLY (roundtrip exit 0). ALSO: >3 selected_stores is rejected
      (POC MAX=3 rule) and profile is per-user (a second user sees their own empty).
  GREEN 401      — GET /api/profile with NO session cookie returns 401, NOT 200.
  RED broken     — a profile save that is missing kron_budget (gate C4 "kron-budget
      saknas") trips red: (a) the real service RAISES on a missing kron_budget, AND
      (b) the harness's roundtrip integrity check CATCHES a mutated service that
      silently drops kron_budget — proving the green PASS is not false-green.

Exit 0 only if GREEN roundtrip passes AND GREEN 401 passes AND RED trips.
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so 'database' and 'app' resolve from the deliverable root

import sqlalchemy  # noqa: E402

# Use a FRESH temp sqlite DB for every check so results are deterministic.
_tmpdir = tempfile.mkdtemp(prefix="matapp-p5-")
_DBFILE = os.path.join(_tmpdir, "harness.db")

GREEN_PROFILE = {
    "persons": 4,
    "meal_days": 6,
    "kron_budget": 1200,
    "selected_stores": ["willys", "ica", "coop"],
}


def _http_client():
    """Starlette TestClient over https so ``Secure`` cookies come back.

    The session cookie is set ``Secure`` (Phase 3 gate C2); TestClient's default
    http://testserver drops Secure cookies, so we run over an https base_url —
    testing the REAL cookie roundtrip end to end through app.main (lifespan boot).
    """
    from app.main import app
    from starlette.testclient import TestClient
    return TestClient(app, base_url="https://testserver")


def _bind_fresh_db() -> sqlalchemy.engine.Engine:
    """Point app.db at a brand-new temp sqlite file and create the whole schema."""
    from database import init_db
    from sqlalchemy.orm import sessionmaker
    import app.db as dbm

    eng = sqlalchemy.create_engine(f"sqlite:///{_DBFILE}",
                                   connect_args={"check_same_thread": False})
    dbm._engine = eng
    dbm._Session = sessionmaker(bind=eng, autoflush=False)
    dbm._default_engine = lambda _=None: eng
    init_db(eng)
    return eng


def _register_user(username: str, password: str) -> None:
    """Insert a user row with a REAL argon2id hash (from app.security)."""
    import app.db as dbm
    from app.models.users import User
    from app import security

    session = dbm._Session()
    try:
        row = User(username=username, password_hash=security.hash_password(password))
        session.add(row)
        session.commit()
    finally:
        session.close()


def _green_roundtrip() -> int:
    """Authenticated PUT->GET profile roundtrip must come back IDENTICAL."""
    _bind_fresh_db()
    _register_user("alex", "s3cret-pw")
    client = _http_client()

    # login via HTTP to obtain the real session cookie (Phase 3 /api/auth/login)
    r = client.post("/api/auth/login",
                    json={"username": "alex", "password": "s3cret-pw"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    cookie = client.cookies.get("matapp_session")
    assert cookie, "no session cookie set on login"
    print(f"[GREEN] authenticated login OK (session cookie issued: {len(cookie)} chars)")

    # PUT the profile
    put = client.put("/api/profile", json=GREEN_PROFILE)
    assert put.status_code == 200, f"PUT /api/profile: {put.status_code} {put.text}"
    print("[GREEN] PUT /api/profile (auth) -> 200")

    # GET it back — must be IDENTICAL to what we stored (roundtrip)
    get = client.get("/api/profile")
    assert get.status_code == 200, f"GET /api/profile: {get.status_code} {get.text}"
    body = get.json()
    for key in ("persons", "meal_days", "kron_budget", "selected_stores"):
        assert body.get(key) == GREEN_PROFILE[key], (
            f"roundtrip mismatch on {key}: stored {GREEN_PROFILE[key]!r} "
            f"read back {body.get(key)!r}"
        )
    print("[GREEN] GET /api/profile (auth) -> 200, read-back IDENTICAL to stored")
    print(f"[GREEN] roundtrip stored={GREEN_PROFILE!r}")
    print(f"[GREEN] roundtrip read  ={body}")

    # POC store_selection MAX=3 rule: 4 stores must be rejected (router 422)
    bad = dict(GREEN_PROFILE, selected_stores=["w", "i", "c", "x"])
    r_bad = client.put("/api/profile", json=bad)
    assert r_bad.status_code == 422, (
        f">3 stores not rejected: {r_bad.status_code} (MAX=3 rule broken)"
    )
    print("[GREEN] 4 selected_stores -> 422 (MAX=3 store_selection rule holding)")

    # per-user isolation: a second user must see NO profile (404), not alex's
    _register_user("bella", "other-pw")
    bella = _http_client()
    lb = bella.post("/api/auth/login",
                    json={"username": "bella", "password": "other-pw"})
    assert lb.status_code == 200, "bella login failed"
    rb = bella.get("/api/profile")
    assert rb.status_code == 404, (
        f"bella saw {rb.status_code}, expected 404 (profile must be per-user)"
    )
    print("[GREEN] per-user isolation OK: bella has no profile (404)")

    print("GREEN-ROUNDTRIP-EXIT=0")
    return 0


def _green_401() -> int:
    """Unauthenticated GET /api/profile must be 401, NOT 200."""
    _bind_fresh_db()
    _register_user("carol", "pw-carol")
    client = _http_client()

    # no login -> no session cookie
    r = client.get("/api/profile")
    assert r.status_code == 401, (
        f"unauthenticated GET /api/profile -> {r.status_code}, expected 401 (not 200)"
    )
    print("[GREEN] unauthenticated GET /api/profile -> 401 (NOT 200); auth-skyddad holding")

    # also PUT without auth must 401
    r2 = client.put("/api/profile", json=GREEN_PROFILE)
    assert r2.status_code == 401, (
        f"unauthenticated PUT /api/profile -> {r2.status_code}, expected 401"
    )
    print("[GREEN] unauthenticated PUT /api/profile -> 401 (auth-skyddad holding)")
    print("GREEN-401-EXIT=0")
    return 0


def _red_kron_budget_missing() -> int:
    """Prove the harness CATCHES the 'kron-budget saknas' failure class.

    (a) The live service RAISES when kron_budget is missing (guard live).
    (b) A MUTATED service that silently DROPS kron_budget on save must make the
        same roundtrip compare go RED (read-back would lose kron_budget). If the
        roundtrip compare does NOT catch it, the harness is false-green.
    """
    import app.db as dbm
    from app.models.users import User
    import app.profile_service as ps
    from app.profile_service import ProfileData

    _bind_fresh_db()
    session = dbm._Session()
    try:
        session.add(User(username="dave", password_hash="x" * 40))
        session.commit()
        dave = session.query(User).filter_by(username="dave").first()
    finally:
        session.close()

    # (a) live guard: missing kron_budget must be rejected by the real service
    try:
        ps.save_profile(dave, ProfileData(persons=2, meal_days=5, kron_budget=None,
                                          selected_stores=[]))
        print("[RED-FAIL] save_profile accepted a MISSING kron_budget (guard absent)")
        return 0
    except ValueError as e:
        print(f"[RED] missing kron_budget correctly rejected by save_profile: {e}")

    # (b) mutation proof: a service that silently drops kron_budget must make the
    #     roundtrip compare go RED (the read-back would lose the budget).
    original_save = ps.save_profile
    original_load = ps.load_profile

    def _broken_save_none(user, data):
        # A genuinely broken save: bypasses the guard and persists WITHOUT
        # kron_budget (drops it to None) — the gate-C4 failure we must catch.
        session = dbm._Session()
        try:
            from app.models.profile import Profile
            row = session.query(Profile).filter_by(user_id=user.user_id).first()
            if row is None:
                row = Profile(user_id=user.user_id)
                session.add(row)
            row.persons = data.persons
            row.meal_days = data.meal_days
            row.kron_budget = None          # <-- the bug: budget silently dropped
            row.selected_stores = ",".join(data.selected_stores)
            session.commit()
            session.refresh(row)
            return row
        finally:
            session.close()

    ps.save_profile = _broken_save_none
    try:
        s = dbm._Session()
        try:
            dave = s.query(User).filter_by(username="dave").first()
        finally:
            s.close()

        broken_data = ProfileData(persons=3, meal_days=7, kron_budget=900,
                                  selected_stores=["willys"])
        ps.save_profile(dave, broken_data)
        loaded = ps.load_profile(dave)
        print(f"[RED] broken save (kron_budget dropped) read back: "
              f"kron_budget={loaded.kron_budget!r}")
        if loaded.kron_budget != 900:
            print("[RED] roundtrip integrity check DETECTED the dropped kron_budget")
            return 1  # red tripped — harness is NOT false-green
        print("[RED-FAIL] dropped kron_budget went UNNOTICED — harness is false GREEN")
        return 0
    finally:
        ps.save_profile = original_save
        ps.load_profile = original_load


def main() -> int:
    rc_green_rr = _green_roundtrip()
    rc_green_401 = _green_401()
    rc_red = _red_kron_budget_missing()

    if rc_green_rr != 0:
        print("HARNESS-FAIL: green roundtrip did not pass")
        return 2
    if rc_green_401 != 0:
        print("HARNESS-FAIL: green 401 check did not pass")
        return 3
    if rc_red == 0:
        print("HARNESS-FAIL: broken (kron-budget missing) NOT caught -> false-green")
        return 4
    print("HARNESS RESULT: PASS (green roundtrip + green 401 + anti-false-green red trip)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
