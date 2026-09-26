# T4b — menu reads the offers DB + week param + boot ingest (MC 1355.5)

Parent: MC 1355 · Repo: `/srv/workspace/svarkor-matapp-audit-2026` (branch `main`)
Commit: **b06c30935eb03b59f3492e412b0f0456a9b17600** — `matapp: menu from offers DB + week param + boot ingest (MC 1355.5)` (not pushed)

## Diff summary (12 files, +399/−120)

| File | Change |
|---|---|
| `src/planner/weeks.py` (NEW, 46 lines) | THE one shared week-math helper: `week_to_monday` (validates REAL ISO weeks via `date.fromisocalendar` — rejects `W00`/`W54`/`9999-W99`/`0000-W01` with `ValueError`, never OverflowError, never silent extrapolation) + `current_week_key`. Kills the P2-4 duplication. |
| `src/planner/menu.py` | local `_week_to_monday` copy deleted; imports the shared helper. Stale `_WEEK_RE` line removed. |
| `app/optimizer/optimizer.py` | same: local `_week_to_monday` copy deleted, shared helper imported. |
| `app/routers/menu.py` | `GET /api/menu` now takes optional `week` (pattern `^\d{4}-W\d{1,2}$`, default = current ISO week); non-real weeks → **422**. Offers read from the offers DB via `list_offers_in_week(session, week)`, filtered to the user's selected stores (`store_selection`; empty selection = no filter), planned by the motor's `src.planner.menu.plan_menu` (3 seeds). Response shape kept: `week_key`, `suggestions[]` with `days[]` (`date`, `dish_id`, `andel_extrapris`, `used_offer_ids`). The hardcoded `app/optimizer/offers.py` fixture is no longer the menu's data source. |
| `app/main.py` | lifespan runs `run_boot_ingest()` = `scheduler.periodic.main(cfg=get_planner_config(), db_url=db.db_url())` — boot-time only, NO background thread/timer. Fail-tolerant: exception → `logger.warning(..., exc_info=True)` + boot continues. |
| `app/db.py` | new `db_url()` seam: bound engine's URL (tests' temp DB) else `database.default_url()` — ONE url source so the boot ingest writes the DB the app reads. |
| `database.py` | default-URL logic extracted to `default_url()` (reused by `app.db.db_url`). |
| `src/offers_db/store.py` | canonical single definition of the `offers` table; reference-price columns (`regular_price_cents`, `savings_cents` — closure-gap 1) moved here. |
| `app/models/offers_db.py` | duplicate table mapping RETIRED → re-export shim of the motor's `Offer` (two mappings of one tablename on the shared Base raised `InvalidRequestError` the moment the menu router imported the motor store). |
| `src/scheduler/periodic.py` | imports unified to the `src.*` package spelling (repo root is on `sys.path` in both motor and app contexts). |
| `src/normalizer/chain_mapper.py` | dual import seam for `CHAIN_MAP` (app context `src.config`, motor context `config`). |
| `tests/test_menu_wiring.py` (NEW, 193 lines) | offline regression tests (below). |

## Test evidence (fresh, clean `__pycache__`/`.pytest_cache`)

```
/srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q
41 passed, 1 warning in 5.07s
EXIT=0
```

New regression tests (`tests/test_menu_wiring.py`, all offline, offers DB seeded via `upsert_week`):
- `test_menu_with_seeded_offers_has_used_offer_ids` — seeded menu carries non-empty `used_offer_ids`
- `test_menu_invalid_week_is_422` — `2026-W54`, `2026-W00`, `9999-W99`, `0000-W01`, `notaweek`, `26-W5` → all 422
- `test_menu_empty_offers_db_degrades_200` — empty DB → 200, every day `used_offer_ids: []`
- `test_selected_store_filter_restricts_offers` — only `ica` selected → no willys offer id in any plan
- `test_boot_ingest_populates_offers_db` — lifespan ingest wiring writes normalized offers into the app DB (fake `pull_grocer`, no network)
- `test_boot_ingest_failure_is_fail_tolerant` — raising ingest → boot continues, `/health` 200

## TestClient probe table (executed this session, PROBE_EXIT=0)

| Probe | Request | Result |
|---|---|---|
| 1. menu with seeded offers | `GET /api/menu?week=2026-W37` (2 willys rows seeded) | **200**, `week_key: 2026-W37`, 3 suggestions, `used_offer_ids: [1, 2, 1, 2, 1, 2]` (non-empty) |
| 2a. `week=2026-W54` | `GET /api/menu?week=2026-W54` | **422** |
| 2b. `week=2026-W00` | `GET /api/menu?week=2026-W00` | **422** |
| 2c. `week=9999-W99` | `GET /api/menu?week=9999-W99` | **422** (was OverflowError 500 — BUG-1) |
| 2d. `week=0000-W01` | `GET /api/menu?week=0000-W01` | **422** (was silent 2027 extrapolation — BUG-2) |
| 3. empty offers DB | `GET /api/menu?week=2026-W37` (fresh empty DB) | **200**, 15 days, all `used_offer_ids: []` (N5 degradation, no 500) |

## Notes / open items

- `andel_extrapris` is kept in the response for shape compatibility; the offers DB has no reference-price column populated by the current ingest, so it computes to 0.0 from DB rows — the ratio rule still lives in `app/optimizer/optimizer.py` for callers that supply reference prices.
- Boot ingest is boot-time only per DoD; a periodic refresh is a later card.
- `src/normalizer/chain_mapper.py` still has its own `iso_week_bounds` (week-window math, a different concern from key→Monday); not in this card's stated dedup scope.

# VERDICT: PASS
