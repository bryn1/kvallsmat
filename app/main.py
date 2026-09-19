"""app.main — FastAPI app assembly for the matapp framtidsvision (Phase 7 T6 api-lager).

Assembles the FastAPI app and includes the /api/auth router (Phase 3), the
/api/profile router (Phase 5, auth-skyddad) and the /api/menu router (Phase 7,
auth-/profil-skyddad). On startup it runs boot() (Phase 2 db-foundation) so the whole
schema (users, profile, offers, ...) exists against the shared database.Base before any
request handling — POC fix-2 idiom.

Phase 7 scope: auth (Phase 3) + profile (Phase 5) + menu (Phase 7 api-lager).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db as db
from app.routers import auth, menu, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.boot()
    yield


app = FastAPI(title="matapp framtidsvision", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(menu.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "matapp",
            "auth": "argon2id+session", "profile": "auth-protected",
            "menu": "auth+profile-protected"}
