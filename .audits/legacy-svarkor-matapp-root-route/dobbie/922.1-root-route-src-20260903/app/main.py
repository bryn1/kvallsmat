"""C1 — web main: FastAPI app assembly + static/boot wiring (484.3 T3).

  * Assembles the app, mounts /static, includes the stores + menu routers.
  * Runs boot() (C2) on startup — schema on the motor's shared Base + idempotent
    seed — against the SAME sqlite file the motor writes.
  * GET /health reports {status, app, motor, motor_resolved}.

FIX 2 (model-import order): the web model modules (store_selection imports the
motor's shared Base) are imported at MODULE scope here, BEFORE boot() runs —
so all tables (motor's + store_selection) exist on Base before create_all.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.config as app_config
import app.db as db
from app.routers import menu, stores

# FIX 2: import web model modules BEFORE boot so their tables register on Base.
import app.models.store_selection  # noqa: F401,E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.boot()
    yield


STATIC_DIR = os.path.join(app_config.PROJECT_ROOT, "static")
TEMPLATES_DIR = os.path.join(app_config.PROJECT_ROOT, "templates")
app = FastAPI(title="Kvällsmats mallrecept + butiker", lifespan=lifespan)

app.include_router(stores.router)
app.include_router(menu.router)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def root() -> FileResponse:
    """Serve the menu-ui shell (templates/index.html) at the site root and /index.html."""
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": "kvallsmats",
        "motor": app_config.MOTOR_RESOLVED,
        "motor_resolved": app_config.MOTOR_RESOLVED,
    }
