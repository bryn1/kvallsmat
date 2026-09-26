"""DoD5 native-boot test (484.3-gate 484.5 fix).

Proves the store-selection round-trip works on the LITERAL natively-booted
artifact — stock `app.config`, NO external harness injection (no conftest
`booted_db` fixture touching PLANNER).

Approach: run a FRESH python subprocess with only this package root on
PYTHONPATH (app.config does R1 motor resolution itself), import app.config,
assert its *native default* PLANNER carries the real store catalog, then run
the full stores round-trip (GET /api/stores -> POST select -> GET selected)
against app.main:app booted to a scratch DB.

This is the regression the gate 484.5 flagged: before the fix, native PLANNER
was `PlannerConfig()` (empty grocers), so /api/stores returned [] on the
shipped product and DoD5 could not be demonstrated.
"""
from __future__ import annotations

import os
import subprocess
import sys

REAL_CHAINS = {"ica", "willys", "coop"}  # the motor CHAIN_MAP chains the app ships

WEB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # kvallsmat-web/

# Python "set literal" of the real chains, e.g. {'coop','ica','willys'}
CHAIN_REPR = "{" + ",".join("'%s'" % c for c in sorted(REAL_CHAINS)) + "}"


def _native(pycode: str) -> tuple[int, str, str]:
    """Run pycode in a fresh interpreter, cwd=kvallsmat-web, only the package on PYTHONPATH."""
    env = dict(os.environ)
    env["PYTHONPATH"] = WEB_ROOT
    env.pop("KVALLSMATS_GROCERS", None)  # ensure we test the DEFAULT, not an override
    env.pop("KVALLSMATS_DB_URL", None)
    proc = subprocess.run(
        [sys.executable, "-c", pycode],
        capture_output=True, text=True, env=env,
        cwd=WEB_ROOT,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_native_planner_carries_real_catalog():
    """Native module boot (no harness) must default PLANNER to the real chains."""
    code = (
        "R = @@REAL@@\n"
        "import app.config as ac\n"
        "from app.config import get_planner_config\n"
        "cfg = get_planner_config()\n"
        "ids = [g.grocer_id for g in cfg.grocers]\n"
        "chain_set = set(ids)\n"
        "assert chain_set, 'native PLANNER has NO grocers'\n"
        "assert R <= chain_set, ('catalog missing real chains: ' + str(R - chain_set))\n"
        "print('NATIVE_CHAINS=' + ','.join(sorted(ids)))\n"
    ).replace('@@REAL@@', CHAIN_REPR)
    rc, out, err = _native(code)
    assert rc == 0, f"rc={rc}\nstdout:\n{out}\nstderr:\n{err}"
    assert "NATIVE_CHAINS=" in out, f"no native chain marker: {out}"


def test_native_stores_roundtrip_do5():
    """On the natively-booted app (stock config), GET stores / POST select /
    GET selected must all work — this is exactly the DoD5 the gate failed."""
    code = (
        "R = @@REAL@@\n"
        "import tempfile, os\n"
        "os.environ['KVALLSMATS_DB_URL'] = 'sqlite:///' + tempfile.mktemp(suffix='.db')\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as c:\n"
        "    r0 = c.get('/api/stores')\n"
        "    assert r0.status_code == 200, r0.text\n"
        "    catalog = r0.json()\n"
        "    ids = {s['store_id'] for s in catalog}\n"
        "    assert ids, 'native /api/stores returned EMPTY catalog'\n"
        "    assert R <= ids, ('catalog missing real chains: ' + str(R - ids))\n"
        "    pick = sorted(R & ids)\n"
        "    rs = c.post('/api/stores/select', json={'store_ids': pick})\n"
        "    assert rs.status_code == 200, rs.text\n"
        "    assert set(rs.json().get('selected', [])) == set(pick), rs.text\n"
        "    rg = c.get('/api/stores/selected')\n"
        "    assert rg.status_code == 200, rg.text\n"
        "    got = [s['store_id'] for s in rg.json()]\n"
        "    assert set(got) == set(pick), 'selected mismatch'\n"
        "    print('DO5_OK stores=%d selected=%s' % (len(catalog), sorted(got)))\n"
    ).replace('@@REAL@@', CHAIN_REPR)
    rc, out, err = _native(code)
    assert rc == 0, f"rc={rc}\nstdout:\n{out}\nstderr:\n{err}"
    assert "DO5_OK" in out, f"no DO5_OK marker: {out}"
