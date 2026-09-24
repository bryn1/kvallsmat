"""app.config — runtime config for the web-api layer (ported from the deployed
hosting copy, MC 1355.3 T3; origin: hosting/apps/matapp app/config.py).

Single responsibility carried over from the deployed copy: the store catalog is
READ from the motor's PlannerConfig grocers at request time via
get_planner_config() (O1 pin — the motor's config, not an app constant, is the
source of truth). PLANNER is the live instance wired at boot to the real store
catalog (ica/willys/coop/lidl — lidl added MC 1355.4), so the shipped product serves a real /api/stores with
NO external harness; tests may rebind it. KVALLSMATS_GROCERS (JSON list)
overrides the default for deployment/seeding.

Adaptation to this tree (MC 1355.3): the motor lives IN-TREE at ``src/`` (the
source repo IS the motor home), so PlannerConfig is imported as
``src.config.PlannerConfig`` instead of the hosting copy's sys.path seam.
The DB URL knob is NOT ported — ``database.make_engine`` (root database.py)
already owns MATAPP_DB_URL; a second URL knob here would be a dead duplicate.
"""
from __future__ import annotations

import os

from src.config import PlannerConfig  # motor's config (in-tree src/ package)

# Repo root (the directory holding app/ and src/).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---- Store catalog source (O1) ----
def get_planner_config():
    """Return the live PlannerConfig being used as the single store/offer source."""
    return PLANNER


# The REAL store catalog this product ships with at boot (DoD5, carried verbatim
# from the deployed copy). These are the same chains the motor's CHAIN_MAP
# defines (ica/willys/coop/lidl). Endpoints follow the motor's GrocerConfig shape;
# 'chain' is the chain key (defaults to grocer_id). O1 is still honored: the
# stores router READS PLANNER.grocers at request time — the motor's
# PlannerConfig remains the single source; this is the production wiring of that
# source, not a second app-side list. KVALLSMATS_GROCERS (JSON list of
# {grocer_id, endpoint, token|chain}) overrides the default for deployment.
_DEFAULT_GROCERS = [
    PlannerConfig.grocer("willys", "https://feeds.willys.se/week", chain="willys"),
    # Real endpoints (MC 1355.4, audit T2): ICA's offers page embeds the weekly
    # offers server-side; Lidl's offers index links the campaign pages.
    PlannerConfig.grocer("ica", "https://www.ica.se/erbjudanden/", chain="ica"),
    PlannerConfig.grocer("coop", "https://feeds.coop.se/week", chain="coop"),
    PlannerConfig.grocer("lidl", "https://www.lidl.se/c/erbjudanden", chain="lidl"),
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
