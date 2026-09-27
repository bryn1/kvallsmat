# T11 security pass — register UI + num_children + kid_friendly (MC 1355.17)

Scope: the T11 design (`/srv/workspace/matapp/.audits/202609260913-e6190a72/T11-design.md`,
commit 4a37157) and the seams it touches: `app/routers/auth.py`, `app/routers/profile.py`,
`app/profile_service.py`, `app/db.py ensure_columns`, `static/js/ui/auth.js`,
`static/js/utils/api.js`, `static/js/ui/profile.js`, `static/js/ui/suggestions.js`.
Out of scope: the whole repo audit (covered by prior runs T7-T10); the recipes scraper's
remote-fetch hardening (unchanged by this design beyond one passthrough field).

Method: adversarial read of the design against the real code, per finding a concrete failure
scenario. Read-only; no code changed.

## Findings (ranked)

| # | Severity | Finding | Location | Evidence / repro |
|---|----------|---------|----------|------------------|
| S1 | LOW (pre-existing, owner-ratified) | Username enumeration: register answers `409 "username already taken"` for existing names, and the design's UI maps it to a visible "Användarnamnet är upptaget" message. Enumeration is inherent to OPEN registration (MC 1355.7, owner-ratified) — the design adds no new exposure, it only surfaces what the API already returns. | `app/routers/auth.py:79-80`, design §a | `curl -X POST .../api/auth/register -d '{"username":"existing","password":"longenough1"}'` → 409 names the collision. No fix in T11; any change (e.g. generic message) would contradict the ratified open-registration UX. |
| S2 | INFO (no action) | 422 register detail is safe to surface: `WeakPassword` messages are static strings ("username must be 1-64 characters", "password must be at least N characters") — no internals, no stack, no DB schema. The design's generic 422 banner text is therefore conservative; showing the server detail would also be safe. | `app/auth_service.py:204-221` | Read of the two raise sites; both messages are literals. |
| S3 | INFO (no action) | `err.response = res` on the shared api.js helpers leaks nothing: the session token lives in an HttpOnly cookie (never readable by JS, `app/security.py` cookie policy), and no auth endpoint returns a token in the body. The attached Response object is same-origin only. | design §a, `static/js/utils/api.js:30-51` | Cookie flags set in `app/routers/auth.py:38-45` from `security.SESSION_*`. |
| S4 | INFO (no action) | New columns are injection-safe: `num_children`/`prefer_kid_friendly` are pydantic-validated ints (ge=0 / 0\|1) reaching the ORM as bound parameters; the `ensure_columns` ALTER strings are compile-time constants with no user input (existing T10e mechanism, unchanged). | design §b/§c, `app/db.py:93-108` | ALTER text is an f-string over the static `_NEW_COLUMNS` tuple only. |
| S5 | INFO (no action) | XSS: the design mandates `textContent`-only rendering for the register error banner and the "Barnvänligt" badge (T10f DA P3-1 idiom). No `innerHTML` seam is introduced. | design §a/§c | Existing precedent `static/js/ui/profile.js:66-73`. |

## Verdict basis

No CRITICAL/HIGH finding. S1 is pre-existing, owner-ratified behaviour recorded so it is not
mistaken for a T11 regression. The design introduces no new endpoint, no new auth path, no
secret handling, and no user input reaching SQL or HTML unsanitised.
