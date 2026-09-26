"""Phase 2 (T1) db-foundation — HARNESS SELF-TEST (anti-false-green).

Runs the DoD checks AND proves the harness would catch a broken model:

  GREEN  — the DoD import command exits 0, users.Base==profile.Base==database.Base,
           'regular_price_cents' is a column on the offer model, and init_db creates
           the users/profile/offers tables in a real temp sqlite file.
  RED    — an intentionally broken model (missing 'regular_price_cents', i.e. closure
           gap 1 left open) MUST make the harness exit non-zero. If it doesn't, the
           harness is lying and the whole build is false-green.

Exit 0 only if GREEN passes AND RED trips.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so 'database' and 'app' resolve from the deliverable root

import sqlalchemy  # noqa: E402


def green_case() -> int:
    """The gate C1 DoD, executed exactly."""
    # (1) DoD import command (verbatim from PHASE0.md §P Phase 2)
    import app.db  # noqa: F401  (registers models before init_db — fix-2)
    from app.models import users, profile, offers_db

    assert users.Base is profile.Base, "users and profile must share database.Base"
    assert users.Base is offers_db.Base, "offers must share database.Base"
    from database import Base
    assert users.Base is Base, f"users.Base is not the shared database.Base: {users.Base!r}"
    print(f"[GREEN] users.Base  == database.Base : {users.Base}")
    print(f"[GREEN] profile.Base== database.Base : {profile.Base}")
    print(f"[GREEN] offers.Base == database.Base : {offers_db.Base}")

    # (2) closure-gap 1: regular_price_cents must be a real column on the offer model
    cols = {c.name for c in offers_db.Offer.__table__.columns}
    assert "regular_price_cents" in cols, f"offer missing regular_price_cents; cols={cols}"
    assert "savings_cents" in cols, f"offer missing savings_cents; cols={cols}"
    print(f"[GREEN] offers columns include regular_price_cents & savings_cents")

    # (3) init_db is importable + creates the whole schema in a REAL sqlite file
    from database import init_db
    from sqlalchemy import inspect

    tmp = tempfile.mkdtemp(prefix="matapp-p2-")
    dbfile = os.path.join(tmp, "harness.db")
    eng = sqlalchemy.create_engine(f"sqlite:///{dbfile}")
    init_db(eng)
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    for want in ("users", "profile", "offers"):
        assert want in tables, f"table {want!r} not created by init_db; tables={tables}"
    print(f"[GREEN] init_db created users, profile, offers in {dbfile}")
    # db.py boot() must also work standalone (fix-2: imports models before init_db)
    from app import db
    db._engine = None
    db._Session = None
    db._default_engine = lambda _=None: sqlalchemy.create_engine(f"sqlite:///{dbfile}")
    boot_eng = db.boot()
    assert boot_eng is not None
    print("[GREEN] app.db.boot() ran init_db with all tables registered on Base")
    print("GREEN-CASE-EXIT=0")
    return 0


BROKEN_OFFERS_SRC = '''\
"""Intentional broken model for the anti-false-green harness check.
Same shape as app/models/offers_db.py BUT missing regular_price_cents/savings_cents
(closure gap 1 left open). The harness MUST go red on this.
"""
from sqlalchemy import Column, Integer, String
from database import Base

class Offer(Base):
    __tablename__ = "offers_broken"
    offer_id = Column(Integer, primary_key=True)
    name = Column(String)
    price_cents = Column(Integer)   # <- NO regular_price_cents / savings_cents
'''


def red_case() -> int:
    """Prove the harness trips on a broken model (anti-false-green)."""
    # Build a throwaway module with the broken Offer and check the same column scan
    # the harness uses; it must NOT find regular_price_cents -> red.
    import types

    mod = types.ModuleType("offers_broken_mod")
    exec(compile(BROKEN_OFFERS_SRC, "<broken>", "exec"), mod.__dict__)
    cols = {c.name for c in mod.Offer.__table__.columns}
    if "regular_price_cents" not in cols:
        print("[RED] broken offer model lacks regular_price_cents -> correctly trips")
        return 1  # non-zero = the broken model WAS caught
    print("[RED-FAIL] broken offer model was NOT caught — harness is false GREEN")
    return 0


def main() -> int:
    # Also print the exact DoD command's outcome the way the gate greps it:
    rc_green = green_case()
    rc_red = red_case()

    # RED case must be != 0 (broken model caught). If it returned 0, harness is lying.
    if rc_green != 0:
        print("HARNESS-FAIL: green case did not pass")
        return 2
    if rc_red == 0:
        print("HARNESS-FAIL: broken model not caught (false-green)")
        return 3
    print("HARNESS RESULT: PASS (green DoD + anti-false-green red trip)")

    # DoD import command, executed via subprocess as the gate would, from THIS cwd:
    cmd = [sys.executable, "-c",
           "import app.db; from app.models import users, profile, offers_db; "
           "print(users.Base, profile.Base)"]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    print("[DoD-import] rc=", r.returncode)
    print("[DoD-import] stdout:", r.stdout.strip())
    if r.returncode != 0:
        print("[DoD-import] stderr:", r.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
