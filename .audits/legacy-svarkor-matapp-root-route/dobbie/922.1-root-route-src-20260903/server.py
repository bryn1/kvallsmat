#!/usr/bin/env python3
"""vm106 service entrypoint for the Kvällsmats web app (matapp) (MC 573.2).

Runs the integrated FastAPI app (app.main:app) with uvicorn, bound to
127.0.0.1:8141 (the manifest port for apps/matapp).

MC 573.2 / known renderer constraint: the hardened unit (ProtectSystem=strict,
ProtectHome) makes the whole git working copy read-only at runtime. Two things
would otherwise write into the repo and crash (OSError 30, read-only) before
the renderer grew `StateDirectory=vm106-app-matapp` (systemd creates and chowns
/var/lib/vm106-app-matapp to appsvc and exports $STATE_DIRECTORY to us):

  1. app/config.py's `DB_URL` default is sqlite:///<PROJECT_ROOT>/.data/kvallsmat.db
     where PROJECT_ROOT is the read-only repo dir. We override the whole URL by
     setting the KVALLSMATS_DB_URL env var (which app/config.py reads with
     os.environ.get) to $STATE_DIRECTORY/.data/kvallsmat.db BEFORE app.main is
     imported, so the DB file + WAL live under the writable state dir.

  2. app/config.py's `MOTOR_REPO` default is an EXTERNAL /srv/workspace/.../motor
     path that does NOT exist on vm106. The assembled pelare vendored the motor
     into THIS app's own ./src (self-contained per the 573 brief), so we set
     KVALLMATS_REPO to this app dir: app/config.py then resolves
     MOTOR_SRC = <this dir>/src == the vendored motor. No external path needed.

  Also: the SQLAlchemy engine (app/db.py) does NOT mkdir its sqlite parent
  directory, so we create $STATE_DIRECTORY/.data here before uvicorn imports
  app.main; the thin os.makedirs shim additionally redirects any relative
  `.data`/`data` mkdir call from the motor into the state dir rather than the
  read-only repo (belt+braces, mirrors apps/hotell/server.py).

With no $STATE_DIRECTORY (local dev, e.g. bare `python3 server.py` outside the
unit) behavior is unchanged: defaults resolve the vendored src/ as the motor and
the DB lands next to the app (created below) -- we still chdir into the app dir
so static/ and templates/ resolve.
"""
import os
import sys
import uvicorn

# WorkingDirectory is already the app dir under the real unit, but chdir here
# too so `python3 server.py` from anywhere (local dev) still resolves static/,
# templates/ and the vendored src/ (used as bare relative paths at runtime).
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

PORT = 8141          # MUST match the `port` field in apps.yaml for apps/matapp
HOST = "127.0.0.1"   # renderer's hardened unit binds the service to loopback
APP  = "app.main:app"

# Self-contained motor: point KVALLMATS_REPO at this app dir so app/config.py
# resolves MOTOR_SRC = <this dir>/src = the vendored motor (never an external
# /srv path that vm106 does not have). Use setdefault so a deployer who pins an
# explicit checkout still wins.
os.environ.setdefault("KVALLMATS_REPO", APP_DIR)

STATE_DIR = os.environ.get("STATE_DIRECTORY")

if STATE_DIR:
    data_dir = os.path.join(STATE_DIR, "data")
    dotdata_dir = os.path.join(STATE_DIR, ".data")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(dotdata_dir, exist_ok=True)

    # Env override read by app/config.py (os.environ.get("KVALLSMATS_DB_URL", ...))
    # -- must be set before app.main/app.config get imported (uvicorn.run below
    # imports APP), so the sqlite file lands in the writable state dir.
    os.environ.setdefault("KVALLSMATS_DB_URL",
                          f"sqlite:///{os.path.join(dotdata_dir, 'kvallsmat.db')}")

    # Belt+braces: redirect any relative os.makedirs("data"/".data", ...) from
    # the motor into the writable state dir, never the read-only repo.
    _real_makedirs = os.makedirs

    def _state_redirected_makedirs(name, mode=0o777, exist_ok=False):
        if name in ("data", "./data"):
            return _real_makedirs(data_dir, mode=mode, exist_ok=True)
        if name in (".data", "./.data"):
            return _real_makedirs(dotdata_dir, mode=mode, exist_ok=True)
        return _real_makedirs(name, mode=mode, exist_ok=exist_ok)

    os.makedirs = _state_redirected_makedirs
else:
    # local-dev fallback: unchanged behavior, DB dir created next to the app.
    os.makedirs(".data", exist_ok=True)

if __name__ == "__main__":
    # reload=False: the service unit owns lifecycle; no file-watch overload.
    uvicorn.run(APP, host=HOST, port=PORT, reload=False, log_level="info")
