"""app.main — FastAPI app assembly for the matapp framtidsvision (Phase 3 T2 auth).

Assembles the FastAPI app and includes the /api/auth router. On startup it runs
boot() (Phase 2 db-foundation) so the schema (users, profile, offers, ...) exists
against the shared database.Base before any request handling — POC fix-2 idiom.

Phase 3 scope: auth only; later phases (api-lager, frontend) add their routers here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db as db
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.boot()
    yield


app = FastAPI(title="matapp framtidsvision", lifespan=lifespan)

app.include_router(auth.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "matapp", "auth": "argon2id+session"}
