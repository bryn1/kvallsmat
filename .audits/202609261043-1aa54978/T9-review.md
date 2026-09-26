# T9 deploy — adversarial accuracy review (MC 1355.11, resume cycle 1)

Reviewer: the producing infra child, acting as devils-advocate inline. A devils-advocate
subagent spawn was attempted and REJECTED by the harness (`Error: subagent depth 2 exceeds
maxDepth 1`) — same outcome as the precedent recorded in this run dir's CYCLES.md (T7a,
2026-09-26). Per that precedent the adversarial re-check ran inline; every claim below was
re-derived from the artifacts, NOT copied from T9-deploy.md.

## R1 — Mirror doctrine (re-run)

`diff -rq /srv/workspace/matapp /srv/workspace/hosting/apps/matapp -x .git -x .audits -x .tmp
-x .data -x __pycache__ -x '*.pyc' -x .pytest_cache -x tests -x LEDGER.md -x README.md`
→ empty, exit 0 (`MIRROR_CLEAN`). The mirror carries nothing the source lacks.

- Retired files in hosting git HEAD: `git ls-files apps/matapp | grep -E
  'base\.css|components\.css|responsive\.css|ui/menu\.js|ui/stores\.js|--help'` → no
  matches (exit 1). On disk: `tests/`, `.audits/`, `--help` all absent (ls: cannot access).
- **Drift found and fixed during this review**: source commit `1b641a5e` (2026-09-26 11:49,
  "DEPLOY.md describes the deployed framtidsversion; drop stale base.css comment — MC 1355.11
  follow-up") landed AFTER the mirror assembly, so source DEPLOY.md + templates/index.html
  had moved ahead of the mirror. Synced (source wins), committed as `ba05925` — which
  mistakenly placed `index.html` at the app root — and corrected in the same session by
  `9eb23a4` ("index.html belongs in templates/, not app root"), both pushed. Post-fix diff:
  clean. The mistake and its correction are recorded here and in CYCLES.md.

## R2 — Hosting git chain (re-run)

- `git rev-parse e4b3d038...^` → `265b7cbd5cd62b4060c837d7fce8b8a188482791` — the rollback
  sha stated in T9-deploy.md IS the deploy commit's parent. VERIFIED.
- `git branch -r --contains e4b3d03` → `origin/main`. Deploy commit is pushed. VERIFIED.
- Author of e4b3d03: `svarkor (matapp-audit) <svarkor@agent-town.local>` (from commit
  output at creation time). VERIFIED.
- Follow-up chain: e4b3d03 → (cron commits) → ba05925 → 9eb23a4 (parent 07afde4, a cron
  commit). Rollback for the deploy itself remains `git revert e4b3d03`.

## R3 — Live journey, fresh credentials (re-run after the follow-up push + 300 s pull window)

- `curl -s https://sibbamala.com/matapp/health` → 200
  `{"status":"ok","app":"matapp","auth":"argon2id+session","profile":"auth-protected","menu":"auth+profile-protected","offers_week":"2026-W39","offers_current_week":279,"offers_by_grocer":{"coop":97,"ica":11,"lidl":60,"willys":111}}`
  — offers signal present, 4 grocers, app is "matapp" (not the old "kvallsmats"). VERIFIED.
- `curl -s https://sibbamala.com/matapp/api/stores` → 200, exactly 4 stores:
  willys, ica, coop, lidl (all enabled). VERIFIED.
- `POST /api/auth/register` with fresh user `dacheck8607` → 200; `GET /api/auth/me` with
  the session cookie → `{"user_id":3,"username":"dacheck8607"}`. VERIFIED.
- `GET /api/menu` (auth'd) → 200, non-empty `used_offer_ids` on all five days:
  `[139,136,167,127,267,258,231,252,46,81]`, `[149]`, `[234,233,90]`, `[141,259,75]`,
  `[135,82]`. VERIFIED.
- Served `index.html` line 7 → `<!-- Single stylesheet: app.css (tokens + components) -->`
  — the NEW comment, proving the follow-up commits (ba05925/9eb23a4) were pulled and
  applied by the vm106 pull timer, i.e. the redeploy after the docs sync restarted clean.

## R4 — Claim-document consistency

- T9-deploy.md's claims were checked against observation: pre-publish verdict, assembly
  summary, boot sanity, commit/push facts, live outputs — all reproduced. Two updates were
  folded back into it: the source follow-up commit 1b641a5e (which resolved the two open
  items the artifact listed) and the ba05925/9eb23a4 sync+fix commits.
- Mirror DEPLOY.md is now the source's canonical version (MC 1355.11 header); its claims
  (offer sources: ICA weeklyOffers JSON, Lidl campaign JSON, Willys+Coop via Tjek squid API;
  boot ingest in the lifespan; menu endpoint contract) match the code paths observed in the
  source tree (`src/fetcher/adapters/{ica,lidl,tjek}.py`, `app/main.py` lifespan).

## Findings

- P4 (resolved this session): mirror/source drift after source follow-up 1b641a5e — synced.
- P4 (process, self-noted): the ba05925 cp misfire was caught by the post-commit diff and
  corrected within the same session before any live impact (docs + HTML comment only).
- No P0/P1/P2 findings. All DoD lines of MC 1355.11 hold under independent re-check.

# VERDICT: PASS
