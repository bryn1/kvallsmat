# T1 — matapp audit @43d1eca: correctness + functionality (MC 1355.1)

Auditor: test profile, 2026-09-24. Runtime: `/srv/workspace/Hotell/.venv/bin/python`
(only working python; argon2-cffi had to be pip-installed into it this session — see P2-1).

## 1. Fresh test run (VERIFIED)

Caches cleaned (`__pycache__`/`.pytest_cache` removed) before both runs.

```
$ /srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q
9 passed, 1 warning in 2.85s        EXIT=0     (run 1)
9 passed, 1 warning in 2.61s        EXIT=0     (run 2 — stability confirmed)
```

First collection attempt FAILED: `ModuleNotFoundError: No module named 'argon2'`
(tests/test_auth_fixround2.py → app/security.py:19). Fixed by
`pip install argon2-cffi` into the shared Hotell venv. The suite is therefore NOT
clean-checkout reproducible without that manual step; requirements.txt does not
list argon2-cffi (checked: it lists fastapi/uvicorn/sqlalchemy/httpx/pytest only).

Test-quality note: the 9 tests cover auth lockout + timing-equalizer only. There are
ZERO tests for the menu endpoint, the profile endpoint, the optimizer ratio filter,
the fetcher, or the normalizer. A regression in the entire menu pipeline would stay
green.

## 2. Routes that exist in the SOURCE repo (VERIFIED via app/main.py + probes)

| Route | Method | Exists in source |
|---|---|---|
| `/health` | GET | yes (app.main + server.py glue) |
| `/api/auth/login` | POST | yes |
| `/api/auth/logout` | POST | yes |
| `/api/auth/me` | GET | yes |
| `/api/profile` | GET/PUT | yes |
| `/api/menu` | GET | yes |
| `/api/stores/select` | POST | **NO — 404.** The stores router exists only in the hosting copy |

## 3. Error-path probe table (VERIFIED, TestClient, logged-in unless noted)

| Probe | Result | Assessment |
|---|---|---|
| GET /api/menu?week=9999-W99 | 200, hardcoded 2026-W37 data | week param silently IGNORED (no such param) |
| GET /api/menu?week=0000-W01 | 200, same | ignored |
| GET /api/menu?week=2026-W54 / W00 | 200, same | ignored |
| GET /api/menu?days=0 / persons=-5 / budget=abc / seed=notanint | 200, same | all ignored — no input surface at all |
| POST /api/stores/select (any body) | 404 | route absent in source |
| GET /api/profile (no profile) | 404 "no profile saved" | correct |
| PUT /api/profile valid | 200, echoes profile | correct |
| PUT /api/profile 4 stores | 422 "at most 3 stores" | correct |
| PUT /api/profile persons=0 | 422 | correct |
| PUT /api/profile missing kron_budget | 422 | correct |
| PUT /api/profile unknown store "butiken-x" | **200 — accepted** | no store whitelist validation |
| PUT /api/profile duplicate stores ["ica","ica","ica"] | **200 — accepted** | no dedup/uniqueness check |
| POST /api/auth/login malformed JSON | 422 json_invalid | correct |
| POST /api/auth/login wrong password | 401 | correct |
| Unauth GET /api/menu, /api/profile, PUT /api/profile | 401 | correct (never 200) |
| Menu after logout | 401 | session truly invalidated |
| DB parent dir missing (BUG-3) | **FIXED** — `database.make_engine` makedirs the parent; engine+schema ok | fixed @43d1eca |
| Feed down (pull_grocer to dead endpoint) | fail-tolerant `entries: []`, no raise | per REV6 contract |
| run_motor.py end-to-end | `MOTOR_OK plan=... offers=4 recipes=18 days=5 digest=0b308db1390cd466`, EXIT=0 | works, mock-only (see §5) |

## 4. Prior-audit bug status (MC 1188.10 BUG-1/2/3)

- **BUG-3 (DB missing parent dir → boot crash): FIXED.** `database.make_engine` now
  `os.makedirs(parent, exist_ok=True)`; probe confirms engine+schema on a missing
  nested path. server.py also redirects data dirs to $STATE_DIRECTORY.
- **BUG-1/BUG-2 (week `9999-W99`/`0000-W01` OverflowError 500; `W54`/`W00` silent
  extrapolation): NOT FIXED at the helper level — but structurally unreachable in the
  source API.** `/api/menu` accepts NO week parameter; `WEEK_KEY = "2026-W37"` is a
  module constant. Direct probe of the helper:
  ```
  9999-W99 -> RAISES OverflowError date value out of range
  0000-W01 -> RAISES ValueError year 0 is out of range
  2026-W54 -> 2027-01-04        (silent extrapolation)
  2026-W00 -> 2025-12-22        (silent extrapolation)
  ```
  The identical `_week_to_monday` logic is duplicated in `src/planner/menu.py:133`
  and `app/optimizer/optimizer.py:167` (and `src/normalizer/chain_mapper.py:28`), so
  the moment anyone wires a week parameter into the API, BUG-1/BUG-2 come back.

## 5. Real vs mock — the menu pipeline end-to-end

Two disjoint pipelines exist; they do NOT meet:

1. **The motor (`src/` + `run_motor.py`)** — REAL wiring: fetcher → aggregate →
   normalizer → offers sqlite (`offers_db.upsert_week`) → recipes seed → planner →
   plan_out.json. VERIFIED running (MOTOR_OK above). BUT the fetcher pulls a fictional
   `{base}/veckans-extrapris` JSON API, and the only feed is `run_motor.py`'s fixed
   in-process mock for week **2026-W34**. Against any real grocer endpoint this
   pipeline ingests nothing (fail-tolerant empty feeds) and produces an empty plan.
   **Mock-dependent end to end.**
2. **The API (`app/`)** — `/api/menu` calls `optimizer.plan_menu(WEEK_KEY, offers(),
   recipes(), ...)`, where `offers()` returns a **hardcoded in-memory list of 12
   offers for 2026-W37** (`app/optimizer/offers.py`) and `recipes()` a hardcoded
   roster. Grep confirms `app/optimizer/*` never imports offers_db or a Session —
   **the API menu path never reads the offers DB the motor writes.** A user today
   CAN log in, save a profile, and get 3 deterministic distinct suggestions (VERIFIED:
   seeds 101/202/303, 3 distinct plans, byte-identical across calls) — but the menu
   is canned data for a week that is not this week, ignores the user's selected
   stores entirely, and no store-selection API exists in the source to select any.

**Answer to "can a user today select stores and get a menu built from offers": NO.**
Store selection does not exist in the source (404), and the menu is built from a
hardcoded constant, not from offers. What works end-to-end is only the mock-fed
motor job.

## 6. Divergence table: source @43d1eca vs hosting copy (VERIFIED via diff -rq)

| File(s) | Source @43d1eca | Hosting copy |
|---|---|---|
| `app/auth_service.py`, `app/security.py`, `app/routers/auth.py`, `app/routers/profile.py`, `app/profile_service.py` | present | **ABSENT** (auth reverted, commit 12e2e30) |
| `app/models/users.py`, `app/models/profile.py`, `app/models/offers_db.py` | present | **ABSENT** |
| `app/optimizer/` (4 modules) | present | **ABSENT** |
| `app/config.py` (KVALLSMATS_GROCERS seam, PLANNER willys/ica/coop) | **ABSENT** | present |
| `app/models/store_selection.py` | **ABSENT** | present |
| `app/routers/stores.py` | **ABSENT** | present |
| `app/db.py`, `app/main.py`, `app/routers/menu.py`, `app/models/__init__.py`, `app/__init__.py` | differ | differ |
| `src/` motor | identical | identical |
| `tests/` | test_auth_fixround2.py present | **tests dir empty (only __pycache__)** |

This is a two-way divergence: each side carries features the other lacks. **Any
publish of either over the other reverts live functionality.** Owner decision
required (rule 2) before any mirror publish.

## 7. File hygiene

- All source files ≤ 262 lines; hard ceiling 400 not exceeded anywhere. One file over
  the ~250 target: `app/optimizer/optimizer.py` (262) — borderline, no header reason,
  P3 note.
- DRY violation: `_week_to_monday` + `_week_dates` duplicated verbatim in
  `src/planner/menu.py` and `app/optimizer/optimizer.py` (P2). `_current_user_or_401`
  duplicated in `app/routers/menu.py` and `app/routers/profile.py` (acknowledged in
  docstrings as a deliberate mirror — P3).
- No TODO/FIXME markers found.

## 8. Ranked findings

- **P0-1 — No store-selection API in source; menu ignores stores entirely.**
  `/api/stores/select` 404; `plan_menu` receives no store filter. The product's
  headline promise (deals from YOUR stores) is unimplementable from this source.
  Blocks any publish (see §6 divergence).
- **P0-2 — Two-way source/hosting divergence.** Publishing either direction reverts
  live functionality (auth on one side, store-selection on the other). Owner ruling
  needed.
- **P1-1 — Menu is canned data.** Hardcoded 2026-W37 offers/recipes in
  `app/optimizer/offers.py`/`recipes.py`; API never reads the offers DB; no week
  parameter exists, so prior BUG-1/BUG-2 are unreachable but the user cannot pick a
  week at all.
- **P1-2 — Profile accepts unknown and duplicate stores** (200 on "butiken-x",
  200 on ["ica","ica","ica"]). When the stores router is (re)unified, this becomes a
  real data-integrity bug.
- **P1-3 — Motor is mock-only.** The `{base}/veckans-extrapris` API is fictional;
  against real grocers the pipeline silently yields empty plans (fail-tolerant by
  design, so nothing errors — the failure is invisible).
- **P2-1 — Suite not clean-checkout reproducible:** requirements.txt omits
  argon2-cffi; fresh venv → collection error.
- **P2-2 — Test coverage gap:** 0 tests for menu/profile/optimizer/fetcher/normalizer;
  the 9 passing tests prove auth only.
- **P2-3 — BUG-1/BUG-2 latent:** unguarded `OverflowError`/silent extrapolation in
  the duplicated week-math helpers; will 500/lie again as soon as a week param is
  wired.
- **P2-4 — DRY:** `_week_to_monday` duplicated in two modules (drift risk — the two
  copies are the exact bug-pair P2-3 lives in).
- **P3-1 — `app/optimizer/optimizer.py` 262 lines** (over ~250 target, no header
  reason).
- **P3-2 — `_current_user_or_401` duplicated** across two routers.

## 9. Verdict

Audit completed: fresh suite run recorded (9 passed, EXIT=0, twice), probe table for
every existing route, divergence documented, real-vs-mock assessed, findings ranked.
The suite runs and the audit is complete — PASS per the task's DoD definition
(PASS = audit completed with findings documented; the findings themselves are the
product).

# VERDICT: PASS
