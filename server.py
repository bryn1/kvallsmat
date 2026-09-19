#!/usr/bin/env python3
"""vm106 service entrypoint for the matapp framtidsversion (MC 1164.7 T9).

Ported from the proven POC entrypoint (MC 573.2, hosting/apps/matapp/server.py):
same $STATE_DIRECTORY rebase (sqlite lives in the writable state dir, never the
read-only repo) and the same KVALLMATS_REPO self-contained-motor seam.

Differences from the POC entrypoint:
  * HOST/PORT come from the environment ($HOST default 127.0.0.1 — the renderer
    proxies /matapp/ to 127.0.0.1:<port>; $PORT must equal the apps.yaml port).
  * The api-lager (app/main.py, Phase 7) ships NO static/health routes, so this
    entrypoint mounts the frontend (templates/index.html at / and /index.html,
    /static) and /health BEFORE uvicorn imports the app.

The api-lager is stdlib+sqlalchemy only; the vendored src/ motor is kept for the
run_motor.py ops job (never imported by app.main).
"""
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

PORT = int(os.environ.get("PORT", "8141"))   # MUST match apps.yaml port for matapp
HOST = os.environ.get("HOST", "127.0.0.1")   # renderer proxies to loopback
APP = "app.main:app"

# Self-contained motor for the run_motor.py ops job (never an external /srv path).
os.environ.setdefault("KVALLMATS_REPO", APP_DIR)

STATE_DIR = os.environ.get("STATE_DIRECTORY")

if STATE_DIR:
    data_dir = os.path.join(STATE_DIR, "data")
    dotdata_dir = os.path.join(STATE_DIR, ".data")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(dotdata_dir, exist_ok=True)

    # DB URL override must exist before app.config/app.db import (uvicorn.run
    # imports APP), so the sqlite file + WAL live under the writable state dir.
    # F1 fix (audit MC 1188): the variable is MATAPP_DB_URL — the name
    # database.make_engine() actually reads (was KVALLSMATS_DB_URL, which made
    # the state-dir override dead and booted the engine at the repo path).
    os.environ.setdefault("MATAPP_DB_URL",
                          f"sqlite:///{os.path.join(dotdata_dir, 'matapp.db')}")

    # Belt+braces: redirect relative data-dir mkdirs out of the read-only repo.
    _real_makedirs = os.makedirs

    def _state_redirected_makedirs(name, mode=0o777, exist_ok=False):
        if name in ("data", "./data"):
            return _real_makedirs(data_dir, mode=mode, exist_ok=True)
        if name in (".data", "./.data"):
            return _real_makedirs(dotdata_dir, mode=mode, exist_ok=True)
        return _real_makedirs(name, mode=mode, exist_ok=exist_ok)

    os.makedirs = _state_redirected_makedirs
else:
    # local-dev fallback (also used by the staged harness): a local db next to app.
    os.makedirs(".data", exist_ok=True)
    os.environ.setdefault("MATAPP_DB_URL",
                          f"sqlite:///{os.path.join(APP_DIR, '.data', 'matapp.db')}")


def _wire_static_and_health(app):
    """Add root/static/health routes to the Phase 7 api-lager app (T9 glue)."""
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = os.path.join(APP_DIR, "static")
    templates_dir = os.path.join(APP_DIR, "templates")
    index_html = os.path.join(templates_dir, "index.html")

    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(index_html)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app": "matapp", "version": "framtidsversion",
                "auth": "argon2id+session", "profile": "auth-protected",
                "menu": "auth+profile-protected"}

    if os.path.isfile(os.path.join(static_dir, "favicon.ico")):
        from fastapi.responses import FileResponse as _FR

        @app.get("/favicon.ico", include_in_schema=False)
        def favicon() -> _FR:
            return _FR(os.path.join(static_dir, "favicon.ico"),
                       media_type="image/vnd.microsoft.icon")


import uvicorn  # noqa: E402

if __name__ == "__main__":
    import app.main as _main
    _wire_static_and_health(_main.app)
    uvicorn.run(APP, host=HOST, port=PORT, reload=False, log_level="info")
