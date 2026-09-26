"""app.main — FastAPI app assembly for the matapp framtidsvision (Phase 5 T4 profile).

Assembles the FastAPI app and includes the /api/auth router (Phase 3) and the
/api/profile router (Phase 5, auth-skyddad). On startup it runs boot() (Phase 2
db-foundation) so the whole schema (users, profile, offers, ...) exists against the
shared database.Base before any request handling — POC fix-2 idiom.

Phase 5 scope: auth (Phase 3) + profile (Phase 5). Later phases (api-lager, frontend)
add their routers here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db as db
from app.routers import auth, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.boot()
    yield


app = FastAPI(title="matapp framtidsvision", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "matapp", "auth": "argon2id+session", "profile": "auth-protected"}
