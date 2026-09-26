# MC 1188.10 — audit: korrekthet — kör sviten, error paths (matapp)

Card: 1188.10 ([type:test], parent 1188, requested_by svarkor) · 2026-09-13 (UTC)
Auditor: gunilla. Adversarial correctness audit of the matapp POC source.

POC source audited: `/srv/workspace/svarkor-matapp-root-route/dobbie/922.1-root-route-src-20260903/`
Hosting copy compared: `/srv/workspace/hosting/apps/matapp/`
Interpreter used: `/srv/workspace/Hotell/.venv/bin/python` (fastapi 0.141.1, pytest 9.1.1,
httpx 0.28.1 — VERIFIED by import printout this session). System python3 (3.12.3) has NO
fastapi/pytest — the venv is the only working runtime on this host for this suite.

## 1. Fresh test-suite run

Stale-artifact trap checked FIRST: all `__pycache__`/`.pytest_cache` under the POC tree
deleted before the run (`find . -name __pycache__ -exec rm -rf` + `rm -rf .pytest_cache`;
post-clean count = 0). VERIFIED.

```
RAN: cd /srv/workspace/svarkor-matapp-root-route/dobbie/922.1-root-route-src-20260903
     /srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q
OUT: 68 passed, 1 warning in 4.27s   (re-run twice, identical)
VERIFY_EXIT=0
```

68 test functions collected (`pytest --collect-only` = "68 tests collected"). The prior
"68 green" claim is CONFIRMED on a fresh run. VERIFIED.

Hosting-copy drift (VERIFIED via `diff -r`, pycache excluded):
- `app/` and `src/` are byte-identical to the POC tree (diff exit 0).
- `server.py`, `run_motor.py` identical.
- TWO frontend files differ: `static/js/utils/api.js` (hosting copy has the MC 1111.1
  prefix-aware `resolveApiBase`; POC has `API_BASE = ''`) and `templates/index.html`
  (hosting copy uses relative asset paths with `?v=<hash>` cache-busting; POC uses
  absolute `/static/...`). These are deploy-layer differences, not correctness drift in
  the audited backend. The hosting copy has NO tests/ directory — the suite lives only
  in the POC tree.

## 2. Error-path table (route → input → behaviour → verdict)

All rows VERIFIED this session via TestClient probes (probe script:
`/home/gunilla/1188.10-probes.py`; raw outputs pasted in the session log).

| Route | Input | Behaviour | Verdict |
|---|---|---|---|
| GET /api/menu | no params | 422, `week: Field required` | OK — handled |
| GET /api/menu | week=`not-a-week` / `2026-W34x` / `abc-W34` / `2026W34` | 422 pattern mismatch | OK — handled |
| GET /api/menu | meal_days=0 / 15, persons=0 / 11 | 422 range errors | OK — handled |
| GET /api/menu | budget_tier=`luxury` | 422 pattern mismatch | OK — handled |
| GET /api/menu | seed=`banana` | 422 int parse error | OK — handled |
| GET /api/menu | week=`9999-W99` | **UNHANDLED OverflowError → 500** (`date value out of range` in `_week_to_monday`) | **BUG-1** |
| GET /api/menu | week=`0000-W01` | 500 (same OverflowError path) | **BUG-1** |
| GET /api/menu | week=`2026-W54`, `2026-W00`, `2021-W53` | 200 — Jan-4 rule silently extrapolates to non-existent weeks (W54→2027-01-04, W00→2025-12-22) | **BUG-2** (silent wrong data, no error) |
| POST /api/stores/select | unknown store_id | 422 `unknown store_id(s)` | OK — handled |
| POST /api/stores/select | 4 stores | 422 `at most 3 stores` | OK — handled |
| POST /api/stores/select | empty list | 200, clears selection | OK (by design) |
| POST /api/stores/select | malformed JSON body | 422 json_invalid | OK — handled |
| GET /api/menu | DB missing (parent dir absent) | **UNHANDLED OperationalError at boot → 500/crash** (`unable to open database file`) | **BUG-3** |
| GET /api/menu | DB file missing, dir exists | 200 — first boot creates schema + seeds | OK |
| Feed down | pull_grocer to unreachable host | fail-tolerant: returns `entries: []`, no raise | OK — handled |
| GET /api/nonexistent | — | 404 | OK |
| GET /static/../server.py | traversal attempt | 404 (Starlette normalizes) | OK |

## 3. Edge cases

- **Empty DB (schema, no seed)**: VERIFIED — `/api/menu` returns 200 with `days: []`
  (planner starved but no crash); `/api/stores` still returns the 3-grocer catalog
  (catalog comes from PlannerConfig, not DB); `/api/stores/selected` returns `[]`.
  Judgement: handled, though an empty menu is silent — no hint that seeding failed.
- **Concurrent requests**: VERIFIED — 20 parallel GET /api/menu (8 threads): all 200;
  20 parallel POST /api/stores/select: all 200. sqlite `check_same_thread=False` +
  short-lived sessions hold up at this scale. No locking errors observed.
- **Missing STATE_DIRECTORY**: VERIFIED via stubbed-uvicorn run of server.py —
  falls back to local-dev mode (`.data` created next to the app, KVALLMATS_REPO set to
  the app dir, uvicorn.run stub printed `app=app.main:app host=127.0.0.1 port=8141`).
  Handled by design.

## 4. Dead code / unreachable branches (app/routers + motor-src)

- **BUG-4 (correctness, user-facing): the `allergens` query param is SILENTLY DROPPED.**
  VERIFIED by monkeypatching `plan_menu` in the router namespace and capturing the
  FamilyPrefs the router actually builds: with `allergens=mjölk` sent (both single and
  repeated-key forms), the captured family has `allergens=()` while `budget_tier` and
  `vegetarian` arrive correctly. Root cause (VERIFIED with a minimal FastAPI 0.141.1
  repro): a pydantic-v2 BaseModel used as a query dependency does NOT collect repeated
  query params into an `Optional[list[str]] = None` field — the field resolves to None
  for ANY wire form (`?allergens=a&allergens=b`, single key, `Query(None)`). A REQUIRED
  `list[str]` field in the same model is instead misread as a BODY param (422 `missing
  body`). The frontend (`static/js/ui/menu.js:38-41`) DOES send `allergens` as repeated
  params and the UI offers a multi-select — so users selecting allergens get plans that
  ignore them. The planner's allergen filter itself is correct (direct `plan_menu` call
  with `allergens=("mjölk",)` excludes mjölk recipes — VERIFIED). Fix direction: declare
  `allergens: list[str] = Query(default=[])` as a function parameter (not via the
  BaseModel), or use `Query(None)` on the endpoint signature.
- `app/routers/stores.py:30` `MAX_SELECTED_REACHABLE = MAX_SELECTED` — defined, never
  referenced anywhere (app, src, tests). Dead constant. VERIFIED by grep.
- `src/planner/menu.py:34` `_WEEK_RE = None  # populated lazily by _week_to_monday` —
  never populated, never read. Dead. VERIFIED by grep.
- `app/routers/menu.py:59` `plan.json() if hasattr(plan, "json") else dict(plan)` —
  `Plan` (dict subclass) has NO `.json` method (VERIFIED: `hasattr(Plan,'json') is
  False`), so the `plan.json()` branch is unreachable and the docstring's claim
  `return plan.json()  # Plan is a dict subclass` is wrong. Harmless (falls through to
  `dict(plan)`) but misleading.
- `src/database.py get_session()` — no caller outside its own module (grep VERIFIED);
  scheduler/tests use `sessionmaker` directly. Unused helper, not a bug.
- `src/recipes/scraper.py` (`scrape_recipes`) — never imported by the web app
  (`app/`, `server.py`, `run_motor.py` grep: no reference). It is exercised by its own
  tests (test_recipe_scraper.py) so it is not dead in the suite, but it is NOT wired
  into the product: recipe-db grows only via the 18-recipe starter seed. Same for the
  whole ingest line (fetcher/normalizer/scheduler): tested as modules, never invoked by
  the web app — offers only enter the DB if something runs `run_motor.py` or
  `scheduler.main` externally. Judgement: architectural gap worth flagging to the
  parent audit (1188), not a correctness bug in what IS wired.
- `server.py` imports `sys` unused; `run_motor.py` imports `tempfile` unused. Trivial.

## 5. Comparison with the framtidsversion tests in 4d220cd

VERIFIED via `git -C /srv/workspace/hosting show 4d220cd`:
- Commit 4d220cd ("matapp: publish framtidsversion — auth (argon2id+session) + profil +
  3-förslags-meny") contains NO tests/ tree for apps/matapp (`git ls-tree -r 4d220cd |
  grep -i test` → nothing; `git log --all -- apps/matapp/tests` → empty). There are no
  framtidsversion tests to compare against — the only suite that exists is the POC
  suite audited above.
- The framtidsversion's `/api/menu` (auth+profile protected, 3 suggestions, pydantic
  response models) is a DIFFERENT API shape from the POC's (open, single plan). Its
  router was REVERTED on the hosting branch (HEAD = 12e2e30 revert of 4d220cd), so the
  POC source audited here is the live shape. Note for the parent audit: the
  framtidsversion menu router hardcodes `WEEK_KEY` from `app.optimizer.offers` — a
  fixed week — which the POC's query-param design supersedes.

## Verdict summary

- Suite: 68/68 green, fresh, VERIFY_EXIT=0. VERIFIED.
- 3 real defects found: BUG-1 (week-key OverflowError → 500 for extreme years),
  BUG-2 (non-existent week numbers silently accepted, wrong dates), BUG-3 (DB parent
  dir missing → unhandled boot crash; mitigated in production by server.py's
  STATE_DIRECTORY makedirs, so vm106 is not exposed — local/bare deployments are).
- 1 user-facing functional bug: BUG-4 allergens param silently dropped (frontend sends
  it, backend never receives it).
- Dead code: 2 dead constants/vars, 1 unreachable branch, 1 unused helper, unwired
  scraper/ingest line (flagged, by design or not — parent audit's call).

VERIFY_EXIT=0
