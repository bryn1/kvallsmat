"""app.main — FastAPI app assembly for the matapp framtidsvision (Phase 7 T6 api-lager).

Assembles the FastAPI app and includes the /api/auth router (Phase 3), the
/api/profile router (Phase 5, auth-skyddad) and the /api/menu router (Phase 7,
auth-/profil-skyddad). On startup it runs boot() (Phase 2 db-foundation) so the whole
schema (users, profile, offers, ...) exists against the shared database.Base before any
request handling — POC fix-2 idiom.

Phase 7 scope: auth (Phase 3) + profile (Phase 5) + menu (Phase 7 api-lager).
MC 1355.5: on startup the lifespan ALSO runs one weekly ingest pass
(scheduler.periodic.main) so the offers DB populates without a manual motor run.
Boot-time only — no background thread/timer (a periodic refresh is a later card).
A startup ingest failure is fail-tolerant: logged, boot continues.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db as db
from app.config import get_planner_config
from app.routers import auth, menu, profile, stores

logger = logging.getLogger("kvallsmat.app")


def run_boot_ingest() -> int:
    """Run ONE weekly ingest pass against the app's own DB (MC 1355.5).

    Uses the live PlannerConfig (O1 — the motor's config is the store source) and
    the SAME DB URL app.db is bound to, so the offers DB the menu reads is the one
    this populates. Raises on failure — the lifespan decides tolerance.
    """
    from src.scheduler import periodic

    return periodic.main(cfg=get_planner_config(), db_url=db.db_url())


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.boot()
    try:
        run_boot_ingest()
    except Exception:  # fail-tolerant: a dead grocer feed must not crash boot
        logger.warning("boot ingest failed — continuing with existing offers DB",
                       exc_info=True)
    yield


app = FastAPI(title="matapp framtidsvision", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(menu.router)
app.include_router(stores.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "matapp",
            "auth": "argon2id+session", "profile": "auth-protected",
            "menu": "auth+profile-protected"}
