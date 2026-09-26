#!/usr/bin/env python3
"""T5 integration driver — wire the REAL M1-M7 motor end-to-end and emit plan_out.json.

This is the phase-2 integration seam that the milestone modules (built by teddy in
T1-T4) do not themselves provide: scheduler.main() does the ingest line (M1->M4),
recipes are seeded (M6) and planned (M5 C6), but nothing concatenates them into a
weekly food plan artifact. This driver concatenates them using the real modules —
no re-implementation, only wiring + a deterministic test-feed seam (the same
httpx-like FakeSession that the module's own test_scheduler.py uses).

Artefacts (real, not mocked):
  - offers are written to a real on-disk sqlite via offers_db.upsert_week      (M4)
  - recipes are seeded into the same db via recipes.seed.seed_starter          (M6)
  - the planner reads offers via list_offers_in_week and recipes via
    c_rdb_list_all — the two real C6 input seams                         (M5, C-OW, C-RDB)
  - plan_out.json is written from the Plan dict; a meta block records the real
    counts read back from the DB.

Run:  PYTHONPATH=src python3 run_motor.py <out_dir> [<week_key>]
Exit: 0 on success; non-zero with a message on any assertion failure.
"""
import sys, os, json, tempfile, hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from config import PlannerConfig
from database import make_engine, init_db
from sqlalchemy.orm import sessionmaker
# Import every ORM-backed module BEFORE init_db so all tables register on Base.
from offers_db.store import list_offers_in_week
from recipes.store import c_rdb_list_all
from recipes.seed import seed_starter, STARTER_ROSTER
from planner.menu import plan_menu, FamilyPrefs
from scheduler.periodic import main as ingest_main

# --- deterministic test-feed seam (httpx-like, matches tests/test_scheduler.py) ---
class _Resp:
    status_code = 200
    def __init__(self, payload): self._p = payload
    def json(self): return self._p

class _FakeSession:
    """Serves a fixed in-week feed per grocer for week 2026-W34 (Mon 17 - Sun 23)."""
    def __init__(self, week_key):
        self.week_key = week_key
        self._feeds = {
            "willys": {
                "offers": [
                    {"external_id": "w-1", "name": "Köttfärs 500g", "price": 59.00,
                     "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
                    {"external_id": "w-2", "name": "Falukorv 600g", "price": 29.90,
                     "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
                    {"external_id": "w-3", "name": "Pannkakssmet", "price": 21.50,
                     "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
                ]
            },
            "ica": {
                "offers": [
                    {"external_id": "i-1", "name": "Vitfiskfilé 500g", "price": 89.00,
                     "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
                ]
            },
        }
    def get(self, url, headers=None):
        for gid, feed in self._feeds.items():
            if gid in url:
                return _Resp(feed)
        return _Resp({"offers": []})


def run(out_dir: str, week_key: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    db_path = os.path.join(out_dir, "kvallsmat_motor.db")
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    Session = sessionmaker(bind=engine)

    # ---- M1->M4 ingest line (real modules, real on-disk DB) ----
    cfg = PlannerConfig(grocers=[
        PlannerConfig.grocer("willys", "https://api.willys.se"),
        PlannerConfig.grocer("ica", "https://api.ica.se", token="t"),
    ], week_override=week_key)
    rc = ingest_main(cfg=cfg, session=_FakeSession(week_key), db_url=f"sqlite:///{db_path}",
                     now=datetime(2026, 8, 20, 12, 0))
    assert rc == 0, f"scheduler.main returned rc={rc}"

    conn = Session()
    try:
        # ---- M6 recipe-db seed (real module) ----
        seeded = seed_starter(conn)
        recipes = c_rdb_list_all(conn)
        recipe_count = len(recipes)
        assert recipe_count == len(STARTER_ROSTER), \
            f"recipe-db count {recipe_count} != STARTER_ROSTER {len(STARTER_ROSTER)}"

        # ---- real C6 input seams: offers read back from DB, recipes from C-RDB ----
        offers = list_offers_in_week(conn, week_key)
        offer_count = len(offers)
        assert offer_count > 0, "no offers survived the ingest line -> planner starved"

        # ---- M5 planner (real module), determinism (N7) checked here ----
        family = FamilyPrefs(meal_days=5, persons=4, vegetarian=False,
                             allergens=(), budget_tier="budget")
        plan_a = plan_menu(week_key, offers, recipes, family, seed=1234)
        plan_b = plan_menu(week_key, offers, recipes, family, seed=1234)
        assert plan_a == plan_b, "planner not deterministic under identical inputs (N7)"

        plan = dict(plan_a)
        assert plan["week_key"] == week_key
        assert isinstance(plan["days"], list) and len(plan["days"]) > 0
        for d in plan["days"]:
            assert {"date", "dish_id", "used_offer_ids"} <= set(d), f"bad day shape {d}"

        # ---- emit plan_out.json ----
        meta = {
            "week_key": week_key,
            "offers_ingested": offer_count,
            "recipes_in_db": recipe_count,
            "days_planned": len(plan["days"]),
            "family": {"meal_days": family.meal_days, "persons": family.persons,
                        "vegetarian": family.vegetarian, "budget_tier": family.budget_tier},
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "plan_digest": hashlib.sha256(
                json.dumps(plan, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16],
        }
        doc = {"meta": meta, "plan": plan}
        out_path = os.path.join(out_dir, "plan_out.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
        print(f"MOTOR_OK plan={out_path} offers={offer_count} recipes={recipe_count} "
              f"days={len(plan['days'])} digest={meta['plan_digest']}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    week_key = sys.argv[2] if len(sys.argv) > 2 else "2026-W34"
    sys.exit(run(out_dir, week_key))
