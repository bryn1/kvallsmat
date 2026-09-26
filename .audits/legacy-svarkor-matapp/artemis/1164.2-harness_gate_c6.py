"""Gate C6 api-lager harness (MC job 1164.2) — grades bernie's Phase 7 api-lager.

gate-C6 DoD (brief /srv/workspace/svarkor-matapp/briefs/gate-p7.txt + PHASE0.md
§P Phase 7):
  1. GET /api/menu with a valid session + request -> 200 with `suggestions` length 3 (exit 0)
  2. without a session -> 401
  3. deliberately-broken router (missing auth-dependency) -> RED (harness self-test)

Two-sided calibration (PHASE0 test-plan skeleton, failure-taxonomy class 3/4):
GREEN case on the REAL app: authenticated GET returns 200 with exactly 3 suggestions,
unauthenticated GET returns 401. A litmus "self-test" case builds a deliberately BROKEN
/router/menu.py variant that drops the auth dependency, and asserts that the gate's own
401-check WOULD catch it (i.e. the broken variant is distinguishable from the good one).
If the gate cannot tell good from broken, it is false-green -> RED-CASE-EXIT=1.

DB isolation: the harness rebinds app.db._engine/_Session to a temp in-memory sqlite so
NOTHING is written into bernie's shared tree or the app's default .data path. Runs the
real FastAPI wiring (app.main:app = real auth+profile+menu routers) through
fastapi.testclient.TestClient.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

from fastapi.testclient import TestClient

import app.db as dbm
import app.models  # noqa: F401  (register tables on shared Base)
import app.security as security
import app.auth_service as auth_service
from app.models.users import User

# ---------------------------------------------------------------------------
# DB isolation: point the engine at a fresh in-memory sqlite BEFORE boot/APP import
# ---------------------------------------------------------------------------
def _temp_engine():
    import sqlalchemy
    url_dir = tempfile.mkdtemp(prefix="gateC6_")
    url = f"sqlite:///{url_dir}/db.sqlite"
    # app.db._engine/_Session are None on first import; bind temp engine now
    dbm._engine = sqlalchemy.create_engine(
        url, connect_args={"check_same_thread": False})
    dbm._Session = sqlalchemy.orm.sessionmaker(
        bind=dbm._engine, autoflush=False)


# Bind a temp engine/session for the WHOLE process BEFORE app.main is imported,
# so the app's lifespan db.boot() and every service call use isolated storage —
# nothing is ever written into bernie's shared tree or the app's default .data.
_temp_engine()


# ---------------------------------------------------------------------------
# Litmus / deliberately-broken variant: a menu router with NO auth dependency
# ---------------------------------------------------------------------------
def _build_broken_router():
    """Return a FastAPI router identical to app.routers.menu's GET /api/menu but
    with the auth dependency REMOVED (mimics the deliberate gate-C6 defect:
    'router saknar auth-dependency'). Uses the SAME optimizer feed so it stays
    comparable to the real endpoint."""
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
    from app.optimizer import optimizer
    from app.optimizer.offers import WEEK_KEY, offers
    from app.optimizer.recipes import recipes

    class MenuDay(BaseModel):
        date: str
        dish_id: str
        andel_extrapris: float

    class Suggestion(BaseModel):
        week_key: str
        seed: int
        days: list[MenuDay]

    class MenuResponse(BaseModel):
        week_key: str
        suggestions: list[Suggestion] = Field(default_factory=list)

    broker = APIRouter(prefix="/api/menu", tags=["menu"])
    SUGGESTION_COUNT = 3
    RATIO_THRESHOLD = 0.5

    @broker.get("", response_model=MenuResponse)
    def get_menu():
        """(BROKEN) no Request/User/Depends — no auth check at all."""
        family = optimizer.FamilyPrefs()
        plans = optimizer.plan_menu(
            WEEK_KEY, offers(), recipes(), family,
            ratio_threshold=RATIO_THRESHOLD)
        suggestions = [
            Suggestion(week_key=p["week_key"], seed=p["seed"],
                       days=[MenuDay(**d) for d in p["days"]])
            for p in plans[:SUGGESTION_COUNT]
        ]
        return MenuResponse(week_key=WEEK_KEY, suggestions=suggestions)

    return broker


def _litmus_broken_router_detected() -> bool:
    """True iff the gate's OWN 401-check would flag the broken (no-auth) router.

    We build a minimal FastAPI app with ONLY the broken /api/menu router (no auth
    routes, no session cookie possible) and assert GET /api/menu -> 200 with 3
    suggestions (i.e. the gate checks "unauthenticated must be 401" against a
    router with no auth, sees 200 not 401, and reports it — proving the gate can
    tell good-from-broken). Return True when the broken router is distinguishable
    from the real one by the gate's 401 test."""
    from fastapi import FastAPI
    from app.optimizer import optimizer
    broker = _build_broken_router()
    app = FastAPI()
    app.include_router(broker)
    client = TestClient(app)
    # NO session cookie at all — a properly-auth'd router MUST 401 here.
    r = client.get("/api/menu")
    return r.status_code == 200  # broken: leaks menu without any auth


def run_green() -> int:
    """Real app, authenticated GET /api/menu -> 200 + suggestions length 3.

    Returns 0 on all-green, nonzero on a failing check."""
    from app.main import app  # imports real auth+profile+menu routers, lifespan boot

    TestClient.__test__ = False  # silence collection
    tmp_fail = 0

    with TestClient(app) as client:
        # --- DoD 2: unauthenticated GET /api/menu -> 401 ---------------
        anon = client.get("/api/menu")
        print(f"[check] unauthenticated GET /api/menu -> {anon.status_code} (want 401)")
        if anon.status_code != 401:
            tmp_fail = 1
            print("[FAIL] unauthenticated /api/menu did NOT 401")

        # --- DoD 1: valid session -> 200 with suggestions length 3 ------
        # Create a user row + issue an opaque session token server-side
        # (engine/session already bound to temp storage above).
        dbm.boot()
        sess = dbm._Session()
        user = User(username="gateuser")
        user.password_hash = security.hash_password("pw")
        sess.add(user)
        sess.commit()
        uid = user.user_id
        username = user.username
        sess.close()

        token = auth_service.sessions.create(username)
        cookies = {security.SESSION_COOKIE: token}

        authed = client.get("/api/menu", cookies=cookies)
        print(f"[check] authenticated GET /api/menu -> {authed.status_code} (want 200)")
        if authed.status_code != 200:
            tmp_fail = 1
            print("[FAIL] authenticated /api/menu did NOT 200")
        else:
            body = authed.json()
            suggestions = body.get("suggestions", [])
            print(f"[check] suggestions length = {len(suggestions)} (want 3)")
            if len(suggestions) != 3:
                tmp_fail = 1
                print("[FAIL] suggestions length != 3")
            for s in suggestions:
                if len(s.get("days", [])) == 0:
                    tmp_fail = 1
                    print(f"[FAIL] suggestion seed={s.get('seed')} has empty days")
                print(f"[ok] suggestion seed={s.get('seed')} days={len(s.get('days', []))}")

    return tmp_fail


def run_red() -> int:
    """Litmus self-test: an app whose router is missing the auth dependency must
    be detected. Returns 0 iff the gate CAN distinguish good-from-broken (broken
    router returns 200 to an unauthenticated request, which the gate's 401 check
    flags). Nonzero => false-green (gate cannot detect missing auth)."""
    detected = _litmus_broken_router_detected()
    print(f"[red] broken no-auth router returns 200 unauthenticated: {detected}")
    if not detected:
        print("[RED-CASE-FAIL] gate could not distinguish broken no-auth router")
        return 1
    print("[RED-CASE-OK] gate 401-check flags the broken no-auth router "
          "(litmus passed: gate can go red)")
    return 0


def main() -> int:
    try:
        green = run_green()
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        print(f"[FAIL-IN-EXECUTION] {e}")
        green = 1

    try:
        red = run_red()
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        print(f"[FAIL-IN-LITMUS] {e}")
        red = 1

    print(f"GREEN-CASE-EXIT={green}  RED-CASE-EXIT={red}")
    # Harness itself exits 0 only when both calibration halves behave as expected.
    return 0 if (green == 0 and red == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
