# matapp — adversarial security audit (MC 1188.9)

Auditor: henrik (general agent). Date: 2026-09-13 (UTC).
Scope: live POC at `/srv/workspace/hosting/apps/matapp/` (HEAD 12e2e30) AND the
future version at commit `4d220cd` (same clone, `/srv/workspace/hosting`).

**Context ruling applied (per brief):** the POC is open-login BY DESIGN — the owner
explicitly ruled the matapp POC shall be open, usable by anyone without login.
"No auth on the POC" is therefore **not a finding** and is not counted below.
The future version (4d220cd) HAS auth (argon2id + session cookie) and is audited on
its own merits.

Method: full read of every Python/JS/HTML file in the POC tree and the 4d220cd tree
(`git show 4d220cd:<path>`), plus empirical verification: the 4d220cd app was staged
to a temp dir, booted with FastAPI TestClient against a temp sqlite DB, and probed
end-to-end (login, cookie attributes, session invalidation, brute-force, error
leakage, stored-XSS sink analysis). The live POC at https://sibbamala.com/matapp/
was probed read-only (GET/HEAD + one junk-creds POST to a 404 route).

## Findings table

| # | Severity | Finding | Location | Status |
|---|----------|---------|----------|--------|
| F1 | **HIGH** | 4d220cd `server.py` sets `KVALLSMATS_DB_URL` under `$STATE_DIRECTORY`, but 4d220cd `database.py`/`app/db.py` read **`MATAPP_DB_URL`** — the state-dir override is dead. Under the real unit (`STATE_DIRECTORY` set, repo read-only via ProtectSystem=strict) the engine resolves to `<repo>/.data/matapp.db` and boot fails: `sqlite3.OperationalError: unable to open database file`. VERIFIED empirically (see Evidence E1). Availability/DoS of the auth version on deploy; also means the DB would silently land in the repo tree on any host where the repo is writable. | `server.py:52-55` vs `database.py:20-22` (4d220cd) | VERIFIED |
| F2 | **HIGH** | 4d220cd login has **no rate limiting / lockout / CAPTCHA**. 50 consecutive bad logins all returned 401 with no lockout (avg 39 ms/attempt). Online brute-force of passwords is unthrottled. Argon2id (19 MiB, t=2) makes each *existing-username* attempt cost ~37 ms, which caps throughput, but there is no lockout, no backoff, and no alerting. | `app/routers/auth.py:36-42` (4d220cd), `app/auth_service.py:56-62` | VERIFIED |
| F3 | **MEDIUM** | 4d220cd username-enumeration **timing oracle**: login against an existing username takes ~37 ms (argon2 verify runs); against a non-existent one ~2 ms (early return). Measured 10× each: 37.4 ms vs 2.2 ms. An attacker can enumerate valid usernames by timing. | `app/auth_service.py:44-52` (4d220cd) | VERIFIED |
| F4 | **MEDIUM** | 4d220cd sessions are **in-memory with no TTL/expiry** (module-level `SessionStore` dict, no expiry field). Consequences: (a) sessions live until process restart or explicit logout — no idle/absolute timeout; (b) a restart silently logs everyone out (availability, not confidentiality); (c) no cap on concurrent sessions per user (5 created in test, all valid). The code itself documents this as Phase-3 scope. | `app/auth_service.py:20-40` (4d220cd) | VERIFIED |
| F5 | **MEDIUM** | 4d220cd `PUT /api/profile` accepts `selected_stores` entries that are **never validated against the store catalog** (any string up to 3 items, arbitrary length — a 10 000-char store id was stored verbatim) and are persisted as a comma-joined string. A store id containing a comma corrupts the roundtrip (split on `,` on load). Data-integrity + stored-payload issue; no HTML sink for it in the shipped frontend (see F6), so not XSS today. | `app/routers/profile.py:47-56`, `app/profile_service.py:33-35,59` (4d220cd) | VERIFIED |
| F6 | **LOW** | 4d220cd `suggestions.js` renders `dish_id` into `innerHTML` without escaping (`${d.dish_id || 'Recept saknas'}`). `dish_id` is a recipe title, which today comes only from the fixed seed roster — but the recipe-scraper (`src/recipes/scraper.py`) inserts titles from external sources; if a scraped title ever contains HTML and reaches a user's plan, this becomes stored XSS. Same pattern exists in the POC (`stores.js` interpolates `store.name`/`store_id` into `innerHTML`; today sourced from server config, not user input). Defense-in-depth finding. | `static/js/ui/suggestions.js:36-40` (4d220cd); `static/js/ui/stores.js:47-65` (POC) | VERIFIED (sink present; attacker-controlled path currently absent) |
| F7 | **LOW** | 4d220cd `PUT /api/profile` with `kron_budget < 0` raises an unhandled `ValueError` → **500 Internal Server Error** with a generic body (no traceback leaked — FastAPI default). The service-layer validation duplicates what pydantic should enforce (`ge=0` missing on the field). Error-handling hygiene; no information disclosure observed. | `app/routers/profile.py:47-56`, `app/profile_service.py:33-35` (4d220cd) | VERIFIED |
| F8 | **LOW** | No CSP meta tag and no SRI on any shipped HTML (both POC and 4d220cd). Combined with F6 this lowers the bar for any future injected-script issue. | `templates/index.html` (both versions) | VERIFIED |
| F9 | **INFO** | `demo_guard` is **absent** from the matapp copy — verified by content search over the working tree, over the 4d220cd tree, and over all history (`git log -S demo_guard` finds it only in hotell/bibliotek commits, e.g. MC 2034.1/.2 public-demo hardening). What it protects elsewhere (per-visitor rate limit on mutating endpoints + demo banner) is exactly the control matapp's POC lacks; its absence is consistent with the POC's by-design openness but means the POC has **no per-visitor rate limit on POST /api/stores/select** (unbounded DB writes by any visitor). | whole matapp tree, all history | VERIFIED |
| F10 | **INFO** | Feed-fetcher (`src/fetcher/grocer.py`): endpoints come from server-side config (`KVALLSMATS_GROCERS` env or the hardcoded willys/ica/coop defaults) — **no user input reaches the URL**, so no SSRF via the HTTP API. Token handling is correct-by-path: tokens live only in `GrocerConfig` from env/config, are sent as `Authorization: Bearer`, never logged, never echoed. **However `pull_grocer` creates `httpx.Client()` with NO timeout** — a hung feed endpoint blocks the ingest pass indefinitely (the scraper's `httpx.get(..., timeout=10.0)` does set one; the fetcher does not). | `src/fetcher/grocer.py:33-35` (POC, same file at 4d220cd) | VERIFIED |
| F11 | **INFO** | File permissions: POC repo `.data/kvallsmat.db` is `0644 artemis:town` in a group-writable tree (`2775`) — world-readable. Contains only seeded recipes/offers (no user data, no credentials — verified table-by-table). The production DB lives under `$STATE_DIRECTORY=/var/lib/vm106-app-matapp` on vm106 (not present on this host, vm105 — could not inspect live; UNVERIFIED on vm106). sqlite has no native encryption; if the future version stores user password *hashes* there, the file should be 0640/0600. | `.data/kvallsmat.db` (POC tree) | VERIFIED (vm105) / UNVERIFIED (vm106) |
| F12 | **INFO** | Stray artifact: `apps/matapp/--help/kvallsmat_motor.db` — `run_motor.py` was invoked with `--help` as `out_dir`, creating a literal `--help` directory containing a test DB (4 offers, 18 recipes, non-sensitive). Cosmetic hygiene; suggests the ops job lacks argument validation. | `apps/matapp/--help/` | VERIFIED |

## Explicitly NOT findings

- **POC open-login** — by design per the owner's explicit ruling (brief context section). Not counted.
- **SQL injection** — none. All DB access goes through SQLAlchemy ORM with bound parameters (`filter_by`, `filter(... == ...)`); no raw `text()`, no string-formatted SQL anywhere in either version (grep-verified: zero hits for `text(`, `.format(`, `%s` SQL patterns).
- **Shell/command injection** — none. Zero uses of `subprocess`, `os.system`, `eval`, `exec`, `shell=True` in either version.
- **Path traversal** — the only file-open from a URL-ish source is the recipe scraper's `file://` adapter (`src/recipes/scraper.py:61`), which is an OPS-side tool (source comes from operator config, not HTTP input); `StaticFiles` mounts are FastAPI's traversal-safe implementation.
- **Secrets in code/logs/config** — none found. Grep over both trees and all matapp history for `secret|token|password|api_key` with literal values: zero hits. The only `token=` literal is `run_motor.py:82` with the dummy value `"t"` against a fake test feed. Tokens arrive via env (`KVALLSMATS_GROCERS` JSON) and are referenced by path, never echoed. No `.env` files in the tree.
- **Error leakage** — 422/401/404 bodies contain only pydantic validation detail (field paths, pattern strings) — no stack traces, no internal paths, no DB schema. The one 500 path (F7) returns a generic body. VERIFIED by probing malformed bodies, bad types, negative values, oversized payloads.
- **Cookie attributes (4d220cd)** — correct: `HttpOnly; Path=/; SameSite=lax; Secure` observed on the live Set-Cookie header (Evidence E2). Token is `secrets.token_urlsafe(32)` (opaque, high-entropy), server-side mapping only. Logout invalidates server-side (old token resolves to None after logout — VERIFIED) and is idempotent. New token per login (no fixation). SameSite=lax + all mutations on POST/PUT = CSRF posture adequate for this design.
- **Auth-protected routes (4d220cd)** — `/api/profile` GET/PUT and `/api/menu` correctly return **401, never 200**, without a session (VERIFIED E2). `/api/auth/me` returns 401 unauthenticated.

## Evidence

All commands run 2026-09-13 on vm105 by henrik. The 4d220cd tree was staged with
`git ls-tree`/`git show` into `/tmp/matapp-4d220cd` and booted with FastAPI
TestClient (deps pinned exactly as `requirements.txt` in a fresh venv).

**E1 — F1 env-var mismatch (VERIFIED):**
```
$ git show 4d220cd:apps/matapp/server.py | grep -n 'DB_URL'
os.environ.setdefault("KVALLSMATS_DB_URL", ...)      # line ~52, STATE_DIRECTORY branch
os.environ.setdefault("MATAPP_DB_URL", ...)          # only in the NO-state-dir branch
$ git show 4d220cd:apps/matapp/database.py | grep -n 'DB_URL'
url = os.environ.get("MATAPP_DB_URL", f"sqlite:///{here}/.data/matapp.db")
# Simulated unit env (STATE_DIRECTORY set, repo read-only):
ENGINE_URL: sqlite:////tmp/matapp-4d220cd-ro/.data/matapp.db   # repo path, NOT state dir
# boot() then fails: sqlalchemy.exc.OperationalError: unable to open database file
# (POC wiring verified correct: POC app/config.py reads KVALLSMATS_DB_URL)
```

**E2 — 4d220cd auth flow (VERIFIED, TestClient):**
```
unauth profile: 401 / unauth menu: 401 / unauth me: 401
bad login: 401 {'detail': 'invalid credentials'}
good login: 200
set-cookie: matapp_session=<43-char token>; HttpOnly; Path=/; SameSite=lax; Secure
me explicit cookie: 200 {'user_id': 1, 'username': 'audituser'}
put profile: 200 (roundtrip identical) / get profile: 200 / menu: 200 (3 suggestions)
logout: 200 -> me with old token: 401; old token resolves after logout: False
tokens differ across logins: True
50 bad logins: all 401, elapsed=1.96s, avg=39.2ms/attempt (no lockout)
avg per attempt: existing=37.4ms ghost=2.2ms (timing oracle)
5 concurrent sessions all valid: True; SessionStore has TTL/expiry: False
```

**E3 — live POC probes (VERIFIED, read-only):**
```
$ curl -s https://sibbamala.com/matapp/health
{"status":"ok","app":"kvallsmats","motor":true,"motor_resolved":true}
$ curl -s '.../api/menu?week=DROP%20TABLE'   -> HTTP 422, pydantic pattern error only
$ curl -s '.../api/menu?week=2026-W37&meal_days=2&persons=2' -> 200 plan JSON
$ curl -s -X POST .../api/stores/select -d '{"store_ids":["nope"]}'
{"detail":"unknown store_id(s): ['nope']"}
# No CSP header, no HSTS observed in response headers (Cloudflare fronted).
```

**E4 — demo_guard absence (VERIFIED):**
```
$ grep -rn -i 'demo_guard' <POC tree>            -> no hits
$ git grep -n -i 'demo_guard' 4d220cd -- apps/matapp -> no hits
$ git log --all -S demo_guard                    -> only hotell/bibliotek commits (MC 2034.1/.2)
```

**E5 — secrets scan (VERIFIED):** grep over both trees + all 8 matapp-touching
commits for `(token|key|secret)\s*=\s*['"][A-Za-z0-9_-]{8,}` → zero hits; the only
literal is the dummy `token="t"` in `run_motor.py:82` against a fake test feed.

**E6 — file permissions (VERIFIED on vm105):**
```
.data/            drwxrwsr-x (2775) artemis:town
.data/kvallsmat.db -rw-r--r-- (0644) artemis:town   # tables: recipes(18), offers(0), store_selection(0)
```

## Severity summary

- CRITICAL: 0
- HIGH: 2 (F1 deploy-breaking DB-path regression in 4d220cd; F2 no login rate limiting)
- MEDIUM: 3 (F3 username-enumeration timing, F4 sessions without expiry, F5 unvalidated profile store ids)
- LOW: 3 (F6 innerHTML sinks, F7 unhandled ValueError → 500, F8 no CSP/SRI)
- INFO: 3 (F9 demo_guard absent, F10 fetcher without timeout, F11 world-readable sqlite, F12 stray `--help` artifact)

## Recommended fixes (priority order)

1. **F1:** in 4d220cd `server.py`, set `MATAPP_DB_URL` (not `KVALLSMATS_DB_URL`) in the `STATE_DIRECTORY` branch — one-line fix, matches what `database.py` actually reads. (Or make `app/db.py` read `KVALLSMATS_DB_URL` like the POC's `app/config.py`.)
2. **F2:** add per-IP/per-username rate limit or exponential backoff on `POST /api/auth/login` (the demo_guard per-visitor limiter from MC 2034.1 is a proven in-fleet pattern).
3. **F3:** run a dummy argon2 verify for unknown usernames to flatten the timing oracle.
4. **F4:** add a TTL to `SessionStore` (timestamp per token, purge on get) and persist sessions if restarts-must-not-logout matters.
5. **F5:** validate `selected_stores` against the store catalog server-side and cap entry length.
6. **F6/F8:** escape interpolated strings in `suggestions.js`/`stores.js` (or set a CSP) before any scraped recipe titles reach users.
7. **F10:** pass `timeout=10.0` to the fetcher's `httpx.Client()`.

VERIFY_EXIT=0
