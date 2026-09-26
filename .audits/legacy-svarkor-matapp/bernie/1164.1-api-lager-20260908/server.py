#!/usr/bin/env python3
"""server.py — uvicorn assembly entrypoint for the matapp api-lager (Phase 7 T6, gate C6).

Phase 7's "server.py-assembly": a thin process entrypoint that runs the assembled
FastAPI app (app.main:app) under uvicorn. It is deliberately SHORT — just wiring —

  * chdirs into this file's directory so the relative sqlite DB path (database.py
    default ``./.data/matapp.db``) and the ``app`` package resolve no matter where
    the process is launched from;
  * binds 0.0.0.0 on $PORT (default 8141 — the apps/matapp manifest port), so a
    later Hosting phase (9/10) can drive it with an injected PORT without code change.

Single concern: process entrypoint. App assembly is app.main; DB boot happens in
FastAPI's lifespan on startup (no explicit call here).
"""
from __future__ import annotations

import os
import uvicorn

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

PORT = int(os.environ.get("PORT", "8141"))
HOST = os.environ.get("HOST", "0.0.0.0")
APP = "app.main:app"

if __name__ == "__main__":
    uvicorn.run(APP, host=HOST, port=PORT, reload=False, log_level="info")
