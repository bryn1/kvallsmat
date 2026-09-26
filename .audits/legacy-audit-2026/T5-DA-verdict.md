# T5 — Devil's advocate verdict over the matapp build (MC 1355.6)

Parent: MC 1355 · Repo: `/srv/workspace/svarkor-matapp-audit-2026` (main, HEAD `b06c309`).
Claim under attack: *"After 5f3bc1d, 49f0914, b06c309, a matapp user can select stores (now
including Lidl) and get a menu for a chosen week built from REAL commercial offers (ICA +
Lidl), with the offers ingested from the real grocer pages at app boot."*

Method: read T1–T4b artifacts, read the diff `git diff 43d1eca..HEAD --stat` (25 files,
+1289/−121), read `app/routers/menu.py`, `app/main.py`, `app/db.py`, `app/security.py`,
`src/offers_db/store.py`, `src/planner/weeks.py`, `src/scheduler/periodic.py`,
`src/fetcher/adapters/*`, `src/normalizer/chain_mapper.py`; ran the suite and a live
TestClient probe (real network boot ingest) this session.

Baseline evidence (VERIFIED, this session):

```
/srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q
41 passed, 1 warning in 5.38s   EXIT=0
```

Probe (TestClient, temp sqlite, real network boot ingest): `/health` 200; boot ingest wrote
**71 offer rows** (ICA + Lidl, week 2026-W39) — the "real offers at boot" claim is REAL and
VERIFIED. Re-running the boot ingest: rows 71 → 71 (idempotent, VERIFIED).

---

## Attack 1 — Offers-DB wiring correctness

- **Store filter restricts correctly.** VERIFIED: `app/routers/menu.py` reads
  `list_selected(session)` and filters `o.grocer_id in selected`; probe with only `ica`
  selected returned zero willys offer ids in any plan. Empty selection = no filter
  (documented in the router docstring). Note the corollary: with `ica` selected the probe
  returned **zero used offers at all** — ICA's 11 parsed offers matched no recipe by token
  overlap. Correct behavior, but it means a single-store selection can silently yield a
  recipe-only menu.
- **Week filter matches ingest semantics — but only for the CURRENT week.** VERIFIED:
  ingest (`periodic.main`) writes only `choose_week()` = the running week (probe: all 71
  rows are `2026-W39`). `GET /api/menu?week=2026-W10` returns **200 with every day
  `used_offer_ids: []`** — a valid past/future week silently degrades to a recipe-only
  plan with no signal that no offers exist for it. Not a 500, not a lie in the response
  shape, but the user cannot distinguish "no offers this week" from "offers exist and
  none matched". **P2.**
- **Boot ingest is idempotent.** VERIFIED: `upsert_week` upserts on the natural UNIQUE
  `(grocer_id, external_id, week_key)`; probe re-ran `run_boot_ingest()` → 71 → 71 rows,
  no duplicates.

## Attack 2 — Silent total failure

**CONFIRMED — this is the strongest refutation of the claim's spirit.** VERIFIED by code
path: both adapters' `get_text` returns `None` on any non-200/exception → adapter returns
an empty feed → `pull_grocer` degrades to empty entries → `periodic.main` does
`if not raw["entries"]: continue` and returns **0** — no exception, so the lifespan's
fail-tolerant `except` never fires, **no warning is logged**, and `/health` reports only
static strings (`{"status": "ok", ...}`) with no offers count. If ICA and Lidl both change
page shape tomorrow, the app boots green, `/health` is 200, and every menu is
recipe-only — invisible. For an owner ask of "offers must actually work", a failure mode
that is *indistinguishable from success* is not acceptable. **P1.**
Minimal fix: in `periodic.main`, log a warning when a configured grocer yields 0 entries,
and add `offers_current_week: <n>` to `/health` (one query). ~10 lines total.

## Attack 3 — The extrapris ratio rule is dead in the API path

**CONFIRMED.** VERIFIED: probe shows every `andel_extrapris` in every suggestion is
**0.0**; the DB rows carry `regular_price_cents=None, savings_cents=None` (grep confirms
no adapter writes them — `src/fetcher/adapters/ica.py` and `lidl.py` never emit a
reference price). `app/optimizer/optimizer.py:87-92` defines extrapris as
`regular_price_cents > price_cents`, so the >=50%-extrapris deal-ranking rule — the
product's core "deals from your stores" promise — never fires on DB-sourced offers. Menus
are planned on token-overlap offer hits only. This is a **P1 regression of the product
promise**, not a cosmetic gap: T4b knew ("kept for shape compatibility") but shipped the
rule dead. Minimal fix: parse ICA `comparisonPrice` and Lidl
`regionsPrices...basePrice` into `regular_price_cents` in the two adapters (both pages
carry the data per T2/T4a); `savings_cents` derives in `upsert_week` or the adapter.

## Attack 4 — Auth/session over real HTTPS

- **Cookie round-trip: OK.** VERIFIED: live `Set-Cookie` header is
  `matapp_session=...; HttpOnly; Path=/; SameSite=lax; Secure`. Starlette's `set_cookie`
  defaults `path="/"` (no explicit path passed in `app/routers/auth.py:35-41`), so the
  cookie scopes to the whole host and round-trips fine behind
  `https://sibbamala.com/matapp/`. (Probe artifact: TestClient's httpx jar drops `Secure`
  cookies over its `http://testserver` base — an explicit `Cookie:` header got 200. That
  is a test-harness artifact, not an app bug.)
- **No registration endpoint — CONFIRMED.** VERIFIED: `POST /api/auth/register` → 404;
  the auth router exposes only `login`/`logout`/`me`; grep finds no CLI/seed/script that
  creates a user. The only way to get an account today is a direct DB insert (what the
  probe had to do). For a deployed app at sibbamala.com/matapp this is a **P1** for
  "functionality to work" — or at minimum an explicit owner decision that accounts are
  admin-seeded. It is not new to these three commits (43d1eca already lacked it), but the
  claim "a matapp user can..." presumes a user exists, and nothing provisions one.

## Attack 5 — What the children missed

- **Double external_id prefix.** VERIFIED: adapters emit `ica-<id>` / `lidl-<productId>`
  (`ica.py:105`, `lidl.py:74`), then `chain_mapper.py:84` prepends `id_prefix` again →
  DB rows are `ica-ica-5004009053`, `lidl-lidl-11000534`. Harmless for uniqueness/
  idempotency but a visible defect and a future join-key hazard. **P2.** One-line fix
  (drop the prefix on one side).
- **Boot ingest does real network I/O inside the lifespan.** VERIFIED (probe: boot
  blocked on live grocer fetches). Fail-tolerant, so boot cannot hang forever only if the
  fetcher's timeouts are sane — acceptable for a PoC, worth a periodic-refresh card.
  **P3.**
- **File hygiene:** all new/changed source files are well under the 400-line ceiling
  (largest: `ica.py` 128 lines); one concern per file holds. No violation.
- Test suite: 41 passed, EXIT=0 (VERIFIED above). No test covers the "both grocers empty"
  silent-green path — consistent with Attack 2 being unseen.

---

## Minimal fixes before deploy

1. **P1 — failure signal:** warn per grocer on 0 entries in `periodic.main`; add
   `offers_current_week` to `/health`. (~10 lines)
2. **P1 — reference price:** parse ICA `comparisonPrice` / Lidl `basePrice` into
   `regular_price_cents` in the adapters so the extrapris ratio rule goes live.
3. **P1 — user provisioning:** add a registration endpoint (or an owner-ratified
   admin-seed path) — without it no real user can exist on the deployed host.
4. **P2 — double prefix:** strip one of the two `ica-`/`lidl-` prefixes.
5. **P2 — week semantics:** either ingest adjacent weeks or return a visible
   `offers_found: 0` flag in the menu response for non-current weeks.

The headline claim itself (select stores incl. Lidl → menu from real ICA+Lidl offers
ingested at boot) is VERIFIED working for the current week with a pre-existing account.
But three P1s — the dead deal-ranking rule, the invisible total-failure mode, and no way
to become a user — stand between this and the owner's "offers must actually work" bar.

# VERDICT: FIX
