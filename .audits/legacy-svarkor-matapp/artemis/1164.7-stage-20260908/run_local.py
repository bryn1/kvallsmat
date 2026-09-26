#!/usr/bin/env python3
"""run_local.py — T9 (MC 1164.7) local staged-serve for pre-publish acceptance.

Starts the ASSEMBLED app (server.py wiring + app.main api-lager + Phase 8
frontend) on 127.0.0.1:$PORT (default 8398) with a FRESH empty sqlite db, and —
because the auth surface is login-only by design (no public registration; gate
C2) — bootstraps a THROWAWAY acceptance user directly through the shipped app's
own service layer (app.db + app.security), the same path the fleet tests use.
The user's password is RANDOMLY GENERATED at boot and written to
acceptance-user.json (0600, git-ignored scratch) so the browser harness can read
it. Nothing here is a deploy credential.

NOT a deploy artifact. Dev/harness entry only; the shipped entrypoint is
server.py.
"""
import json
import os
import secrets
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(APP_DIR, "app-new", "server.py")
CRED_FILE = os.path.join(APP_DIR, "acceptance-user.json")

# Import the shipped entrypoint as a module (side effects: chdir, env defaults,
# makedirs shim) WITHOUT running uvicorn, then wire glue + seed user + serve.
sys.path.insert(0, os.path.dirname(SERVER))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("shipped_entry", SERVER)
entry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entry)

import app.main as _main          # noqa: E402
entry._wire_static_and_health(_main.app)

from app import security  # noqa: E402


def seed_acceptance_user():
    """Create the gate's throwaway user via the app's own hashing+models.

    Password: MATAPP_ACCEPT_PASS if set, else freshly generated. Written (with
    the username) to CRED_FILE 0600 for the local browser harness only.
    """
    import app.db as dbm
    dbm.boot()
    from app.models.users import User
    user = os.environ.get("MATAPP_ACCEPT_USER", "gate")
    pw = os.environ.get("MATAPP_ACCEPT_PASS") or secrets.token_urlsafe(16)
    session = dbm._Session()
    try:
        existing = session.query(User).filter_by(username=user).first()
        if existing is None:
            session.add(User(username=user,
                             password_hash=security.hash_password(pw)))
            session.commit()
            print(f"[run_local] seeded acceptance user {user!r}")
        else:
            print(f"[run_local] acceptance user {user!r} already present")
    finally:
        session.close()
    fd = os.open(CRED_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"username": user, "password": pw,
                   "note": "throwaway local staged-serve credential (MC 1164.7 harness)"}, fh)


if __name__ == "__main__":
    import uvicorn
    seed_acceptance_user()
    port = int(os.environ.get("PORT", "8398"))
    print(f"[run_local] serving assembled matapp framtidsversion on 127.0.0.1:{port}")
    uvicorn.run(_main.app, host="127.0.0.1", port=port, reload=False, log_level="info")
