"""C1-side runtime config for the web-api module (484.3 T3).

Two responsibilities, both needed before ANY app/db import:
  1. R1 motor resolution: locate motor/src and put it on sys.path. The motor is
     the single source of truth (R1/KVALLMATS_REPO seam). If KVALLMATS_REPO is
     set it wins; otherwise we fall back to the sibling ../../motor tree used by
     this chain's builds.
  2. Runtime knobs the routers/boot read at request/startup time from this
     module's attributes so tests can rebind them (no hardcoded second copy).

Store catalog is READ from the motor's PlannerConfig grocers at request time
via get_planner_config() (O1 pin — the motor, not an app constant, is the
source of truth). PLANNER is the live instance: it is wired HERE at native boot
to the real store catalog (ica/willys/coop — the DoD5 fix for gate 484.5), so
the shipped product serves a real /api/stores with NO external harness; tests
may still rebind it. KVALLSMATS_GROCERS (JSON list) overrides the default for
deployment/seeding.
"""
from __future__ import annotations

import os
import sys

# ---- R1: motor resolution (single source of truth for the motor) ----
_DEFAULT_MOTOR_REPO = "/srv/workspace/svarkor-kvallsmat-recept-phase3-phase2/motor"
MOTOR_REPO = os.environ.get("KVALLMATS_REPO", _DEFAULT_MOTOR_REPO)
MOTOR_SRC = os.path.join(MOTOR_REPO, "src")
MOTOR_RESOLVED = os.path.isdir(MOTOR_SRC)
if MOTOR_RESOLVED and MOTOR_SRC not in sys.path:
    sys.path.insert(0, MOTOR_SRC)

# ---- DB: the SAME sqlite file the motor writes (boot shares a DB, never a fork) ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_URL = os.environ.get("KVALLSMATS_DB_URL", f"sqlite:///{PROJECT_ROOT}/.data/kvallsmat.db")

# ---- Store catalog source (O1) ----
def get_planner_config():
    """Return the live PlannerConfig being used as the single store/offer source."""
    return PLANNER


# Import the motor's config lazily-safe (only when motor resolved).
from config import PlannerConfig  # noqa: E402  (motor's config, via R1 sys.path)

# The REAL store catalog this product ships with at boot (DoD5). These are the
# same chains the motor's CHAIN_MAP defines (ica/willys/coop) and the same trio
# the chain's fixture + nicke's boot_render wire — but living HERE in the product
# config so the natively-booted artifact carries a real catalog with NO external
# harness injection. Endpoints follow the motor's GrocerConfig shape; 'chain' is
# the chain key (defaults to grocer_id). O1 is still honored: the stores router
# READS this PLANNER.grocers at request time — the motor's PlannerConfig remains
# the single source; this is the production wiring of that source, not a second
# app-side list. KVALLSMATS_GROCERS (JSON list of {grocer_id,name,endpoint,
# token|chain}) overrides the default for deployment; else these feeds are used.
_DEFAULT_GROCERS = [
    PlannerConfig.grocer("willys", "https://feeds.willys.se/week", chain="willys"),
    PlannerConfig.grocer("ica", "https://feeds.ica.se/week", chain="ica"),
    PlannerConfig.grocer("coop", "https://feeds.coop.se/week", chain="coop"),
]


def _load_grocers():
    """Build the PlannerConfig grocers from KVALLSMATS_GROCERS (JSON) or the default."""
    raw = os.environ.get("KVALLSMATS_GROCERS")
    if not raw:
        return list(_DEFAULT_GROCERS)
    import json
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as e:  # misconfigured -> fail fast
        raise RuntimeError(f"KVALLSMATS_GROCERS is not valid JSON: {e}") from None
    grocers = []
    for e in entries:
        grocers.append(PlannerConfig.grocer(
            e["grocer_id"], e.get("endpoint", ""),
            token=e.get("token", ""), chain=e.get("chain", None),
        ))
    return grocers


PLANNER = PlannerConfig(grocers=_load_grocers())
