# matapp — architecture (kept true by the Architect; layout v2)

Single FastAPI web app + a vendored self-contained "motor" (`src/`). One sqlite
store. Deployed on vm106 under `/matapp/` (nginx strips the prefix; port 8141,
`DEPLOY.md`). Python deps pinned in `requirements.txt`: fastapi, uvicorn,
sqlalchemy, pydantic, argon2-cffi, httpx. No other runtime deps.

## Module map

### Web layer — `app/` (importable only upward into `src/`, never the reverse)
- `app/main.py` — FastAPI assembly; lifespan runs `db.boot()` + one weekly
  ingest pass (`src/scheduler/periodic.main`, fail-tolerant).
- `app/db.py` — engine/session singleton, `init_db`, and `ensure_columns()`:
  the guarded-ALTER migration list `_NEW_COLUMNS` (idempotent, concurrent-boot
  tolerant). New columns ride this mechanism — never a second migration path.
- `app/security.py`, `app/auth_service.py` — argon2id password hashing, opaque
  session tokens (`matapp_session` HttpOnly cookie), `SessionStore`,
  `LoginRateLimiter`.
- `app/routers/auth.py` — `POST /api/auth/register|login|logout`,
  `GET /api/auth/me`. Registration is open (MC 1355.7); register auto-login.
- `app/routers/profile.py` — `GET/PUT /api/profile`. PUT semantics:
  **absent field = unchanged, explicit null = clear** (`model_fields_set`),
  422 on out-of-range. Applies to `postal_code`, `num_children`,
  `prefer_kid_friendly`.
- `app/routers/menu.py` — `GET /api/menu?week=YYYY-Www` (auth-skyddad). Reads
  offers from the offers DB, filters by the user's selected stores, builds
  `FamilyPrefs` from the persisted profile, calls `src.planner.menu.plan_menu`
  once per seed (3 suggestions). Response models: `MenuResponse` →
  `Suggestion` → `MenuDay` (additive fields only; `offer_sources`,
  `kid_friendly`).
- `app/routers/stores.py` — store catalog from the ONE `PlannerConfig`
  (`app/config.py`).
- `app/profile_service.py` — profile CRUD (`ProfileData` value object, one row
  per user, upsert on save).
- `app/optimizer/` — `recipes.py` (the hand-curated `ROSTER` the planner
  actually consumes; mirrors the DB `Recipe` fields — two carriers of one
  entity), `optimizer.py` (`FamilyPrefs`, `DEFAULT_SEEDS = (101, 202, 303)`,
  `andel_extrapris`).

### Motor — `src/` (vendored, self-contained; never imported by anything outside)
- `src/fetcher/` + `src/fetcher/adapters/` — per-chain offer fetchers
  (willys/ica/coop/lidl + Tjek), `aggregate.py`.
- `src/normalizer/` — offer normalization to the `offers` row shape
  (`chain_mapper.py`, per-ingredient `is_extraprice`).
- `src/offers_db/store.py` — the SINGLE canonical `offers` table
  (UNIQUE `grocer_id, external_id, week_key` + store scope), `upsert_week`,
  `list_offers_in_week`.
- `src/planner/menu.py` — `plan_menu`: filter (`_allowed`) → rank by offer-hit
  count → seeded tiebreak → one dish per day, no repeats; pool exhaustion
  truncates the week (never crashes). MC 1355.18: kid-friendly wins TIES when
  `prefer_kid_friendly` is set (boost, not filter).
- `src/planner/weeks.py` — ISO week math (`week_to_monday`), the ONE week
  validator.
- `src/locator/` — postnummer → stores per chain (willys/ica/coop/lidl/geo).
- `src/recipes/` — recipe-db: `store.py` (ORM + `upsert_recipe`),
  `seed.py` (`seed_starter`, idempotent, run only from `run_motor.py` — NOT at
  app boot), `scraper.py` (`file://`/http ingest, drop-not-fail).
- `src/scheduler/periodic.py` — the weekly ingest pass wired at boot.

### Entrypoints
- `server.py` — vm106 service entrypoint: `$HOST`/`$PORT` (default
  127.0.0.1:8141), mounts `templates/index.html` at `/`, `/static`, `/health`,
  then serves `app.main:app`. Sqlite lives under `$STATE_DIRECTORY`
  (`MATAPP_DB_URL` override).
- `run_motor.py` — ops job: full ingest + `seed_starter`. Never imported by
  `app.main`.

## Data flow

1. Ingest (boot + ops): fetcher adapters → normalizer → `offers` DB rows
   (week-scoped, store-scoped).
2. `GET /api/menu`: offers DB → store-selection filter → `plan_menu` over the
   optimizer `ROSTER` → 3 seeded `Suggestion`s (+ `offer_sources`).
3. The planner NEVER reads the recipes DB; the seed/scraper `kid_friendly`
   values are bookkeeping/consistency only (planning reads the roster).

## Auth model

Open registration, argon2id hashes, opaque session cookie (`HttpOnly`),
`current_user` resolves every protected handler → 401 when absent/invalid.
No password reset, no e-mail verification, no lockout change.

## Offer sources (verified endpoints)

| Chain | Source | Endpoint |
|---|---|---|
| Willys | store locator | `https://www.willys.se/axfood/rest/v2/store` |
| ICA | offers + stores | `https://www.ica.se/erbjudanden/`, `https://www.ica.se/e11/public-access-token`, `https://apim-pub.gw.ica.se/sverige/digx/storesearch/v1` |
| Coop | offers + stores | `https://www.coop.se/butiker-erbjudanden/`, `https://proxy.api.coop.se/external/store/stores?api-version=v1` |
| Lidl | offers + stores | `https://www.lidl.se/c/erbjudanden:`, `https://live.api.schwarz/odj/stores-api/v2/myapi` |
| Tjek | offer data | Tjek API via `src/fetcher/adapters/tjek.py` |
| Geocode | Nominatim | `https://nominatim.openstreetmap.org/search` |

## Store-level selection flow (MC 1355.16)

Profile `postal_code` → resolved once at save time (`src/locator`, per-chain
status persisted in `resolved_stores` JSON, never a 500) → `GET /api/menu`
keeps a chain-level offer row (`store_id` NULL = valid everywhere) or a row
scoped to one of the profile's resolved stores → dedup by (grocer_id,
normalized name) preferring the store-level row. No postal code / no resolved
stores → both steps are no-ops (behaviour = pre-T10b).

## Data store

One sqlite file (`MATAPP_DB_URL` / `$STATE_DIRECTORY`). Tables on the shared
`database.Base`: `users`, `profile`, `offers`, `recipes`, `store_selection`
(sessions live in-memory in `auth_service.SessionStore`, not a table). Schema
changes = ORM column + `_NEW_COLUMNS` guarded-ALTER entry
(existing rows read NULL — every reader treats NULL as 0/absent).

## Tests

`tests/` pytest, offline (temp-DB `client` fixture in `conftest.py`, no
network). Run: `/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q`.
