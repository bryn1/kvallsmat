# ARCH closing verdict — T11 build (MC 1355.18), run 202609270403-a1c4dd1d

NOTE: fan-out was mechanically impossible in this session (`subagent depth 2
exceeds maxDepth 1`); the closing phase ran inline in the orchestrating child.

(1) docs/ARCHITECTURE.md vs the actual tree — re-derived from the artifact,
    not from a report:
    * Modules: app/ web layer (main, db, security, auth_service,
      profile_service, routers/{auth,profile,menu,stores}, optimizer/) and
      src/ motor (fetcher+adapters, normalizer, offers_db, planner, locator,
      recipes, scheduler) — all present on disk, names match.
    * Entrypoints: `server.py` ($HOST/$PORT default 127.0.0.1:8141, matches
      DEPLOY.md apps.yaml port 8141) and `run_motor.py` (ops job) — verified
      by reading both files.
    * Deps: requirements.txt pins fastapi/uvicorn/sqlalchemy/pydantic/
      argon2-cffi/httpx — the doc lists exactly these.
    * Ports: 8141 (deploy), live sanity ran on 8971 (documented as a
      one-off local run, not a service port).
    * Data store: one sqlite (`MATAPP_DB_URL`/`$STATE_DIRECTORY`); tables
      re-derived via `grep __tablename__`: users, profile, offers, recipes,
      store_selection — the doc's table list matches after the sessions
      correction (sessions are in-memory `SessionStore`, not a table).
    * Offer-source endpoints: every URL in the doc's table was grepped out of
      `src/fetcher/adapters/*.py` + `src/locator/*.py` this session.
    * Data flow claim "planner never reads the recipes DB" — verified: the
      menu router consumes `app.optimizer.recipes.recipes()`.
(2) File hygiene: largest changed source file 273 lines (app/routers/menu.py,
    < 400 hard ceiling); one concern per file preserved; test files well under
    600; no TODO/FIXME added (grep count 0); no new CSS component system.
(3) Layout v2: every new file is at its convention path — `docs/ARCHITECTURE.md`
    at the project root, four test files under `tests/`, verdicts/CYCLES/DONE
    in `.audits/202609270403-a1c4dd1d/`, scratch under its `.tmp/`. No stray
    sibling dirs created. Git tree clean (all run artifacts committed).

All three hold.

# JUDGED: 72682e8f5648873885c77551ecd2bb63d3ed3fd31fe718e1ba9a40dc675491bd
# VERDICT: PASS
