# ARCH-verdict — MC 1355.20 (T11 arch gate): docs/ARCHITECTURE.md vs the real tree

Repo `/srv/workspace/matapp` (= `/home/svarkor/Matapp`), HEAD 59295c0e5cbf99b24f7bfddc9ce0f8ee9003009c.
All evidence re-read from the artifacts this session. Fan-out note: this session runs at
subagent depth 1 (`maxDepth 1`), so the producing/verifying children could NOT be spawned —
both passes were executed inline by the design profile and every claim below was re-checked
against the files directly (see DONE.md row D0).

## Cycle 1 findings (all fixed in cycle 2, edits to docs/ARCHITECTURE.md only)

- F1 (check 4, FAIL): the doc had NO limitations section — ICA store-scoped ingest
  follow-up, Coop cold-start warm and `num_children` informational-only were absent
  (grep for "limitation" over the pre-fix doc: zero hits; LEDGER.md:60 carries all three).
- F2 (check 5, FAIL): doc line 90 gave Lidl offers URL as `https://www.lidl.se/c/erbjudanden:`
  with a trailing colon; `src/fetcher/adapters/lidl.py:18` `INDEX_PATH = "/c/erbjudanden"`
  has no colon — stale claim.
- F3 (check 1, FAIL): doc said "per-chain offer fetchers (willys/ica/coop/lidl + Tjek)";
  `ls src/fetcher/adapters/` shows only `_common.py ica.py lidl.py tjek.py` — Willys and
  Coop offers ride the ONE Tjek adapter (`tjek.py:3-6`, dealer ids `app/config.py:47,54`).
- F4 (check 5, minor): the Tjek row named no concrete URL; actual endpoint is
  `https://squid-api.tjek.com/v2/catalogs?dealer_id=<id>` (`app/config.py:47,54`).
- F5 (check 2, minor): the Data store section said "shared `database.Base`" without naming
  the repo-root `database.py` (the Base's home) or `app/models/` (the ORM models).

## Per-check verdicts (post-fix, cycle 2)

1. **Named modules exist and do what the doc says — PASS.** `app/main.py:75,85` lifespan
   runs `db.boot()` + one `periodic.main` pass (main.py:10-12, 68-70); `app/db.py:75,87`
   `_NEW_COLUMNS`/`ensure_columns` guarded-ALTER; `app/routers/auth.py:11-12,73` open
   registration MC 1355.7 with auto-login; `app/routers/menu.py:130-160` offers-DB read,
   store filter, `plan_menu`, `offer_sources`; `app/optimizer/optimizer.py:38,47,60`
   `FamilyPrefs`/`prefer_kid_friendly`/`DEFAULT_SEEDS = (101, 202, 303)`; motor chain
   fetcher→normalizer→`src/offers_db/store.py:6,51` (`upsert_week`, UNIQUE
   grocer_id/external_id/week_key + store scope)→`src/planner/menu.py:145-154`
   (kid-friendly wins TIES, boost not filter); `src/locator/__init__.py:22-28` per-chain
   locators fail-tolerant; `src/recipes/` seed/scraper/store present; `src/scheduler/periodic.py:49,103`
   weekly pass + Willys store-scoped ingest.
2. **Every module that matters is named — PASS (after F5 fix).** Tree walked: `app/`
   (main, db, security, auth_service, profile_service, routers/{auth,menu,profile,stores},
   optimizer/, models/), `src/` (config, database, fetcher+adapters+aggregate+grocer,
   normalizer, offers_db, planner/{menu,weeks}, locator/, recipes/, scheduler/), root
   `database.py`, `server.py`, `run_motor.py`, `static/`, `templates/`. Remaining unnamed:
   `src/config.py`/`src/database.py` (motor-internal plumbing, minor) — recorded as
   acceptable, not load-bearing.
3. **Data flow matches code — PASS.** Store-level selection: `menu.py:146-152` chain-level
   row (store_id NULL) or row scoped to resolved stores, dedup preferring store-level;
   `profile_service.py:31-37,100` persists `postal_code`/`resolved_stores`;
   `locator/__init__.py` never-fatal per-chain status. kid_friendly boost on optimizer
   FamilyPrefs: `optimizer.py:47` + `menu.py:149-154` (tie-break, not filter).
   `app/db.py` ensure_columns: verified above.
4. **Known limitations stated honestly — PASS (after F1 fix).** New "Known limitations"
   section (doc lines 106-116) states all three, matching `LEDGER.md:60` and
   `app/routers/profile.py:51-52` ("num_children is INFORMATIONAL in T11").
5. **No secrets, no stale claims — PASS (after F2/F4 fix).** Secret grep over app/ + src/
   (`(api_key|token|secret|password)\s*=\s*['"]…`): zero hits. Every endpoint URL in the
   doc now matches code: willys `src/locator/willys.py:16`; ica `src/fetcher/adapters/ica.py:4`,
   `src/locator/ica.py:14-15`; coop `src/locator/coop.py:34-35`; lidl `lidl.py:18` +
   `src/locator/lidl.py:15`; tjek `app/config.py:47,54`; nominatim `src/locator/geocode.py:14`.

## Omissions list (check 2, resolved)

Fixed this cycle: root `database.py` + `app/models/` now named in the Data store section;
Tjek-dealer relationship (willys/coop via one adapter) now explicit. Left unnamed
(accepted, motor-internal plumbing): `src/config.py`, `src/database.py`, `src/fetcher/grocer.py`
(covered by "aggregate.py + grocer.py drive the pass").

## Test evidence

`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` → **116 passed** (re-run after
the doc edits; doc-only change, no source touched).

# JUDGED: 086fafeca6a569c82d769b76411dac64416f9662256dbb3366757dd6dc854431
# VERDICT: PASS
