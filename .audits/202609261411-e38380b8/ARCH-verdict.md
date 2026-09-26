# ARCH-verdict — T10b design (store-level selection per postnummer), MC 1355.13

Written by the design (arch) child, cycle 1, 2026-09-26. Judged artifact:
`/srv/workspace/matapp/.audits/202609260913-e6190a72/T10b-design.md` (copy in this out dir).

## Placement (workspace-convention v2)
- Design doc lives under `/srv/workspace/matapp/.audits/202609260913-e6190a72/` — the
  existing audit run dir for parent 1355. No new workspace-root dir created. Scratch for
  the future build goes under `/srv/workspace/matapp/.tmp/`.
- `docs/ARCHITECTURE.md` does not exist in the repo yet; T10b's build phase should create
  it (module table + data flow can be lifted from T10b-design.md §2/§6). Not a blocker for
  this design card — flagged as follow-up.

## Decisive checks re-run by this child this session (evidence)
- Design doc exists, last line exactly `# VERDICT: SHIP` — `tail -1` → `# VERDICT: SHIP`.
- All 14 named existing seams exist: 14/14 `OK` (profile/store_selection models,
  profile/stores/menu routers, config, tjek adapter, grocer contract, offers_db store,
  profile_service, db, profile.js, index.html, app.js).
- `src/locator/` does not exist → no collision with the 8 proposed new files.
- `src/offers_db/store.py` is the SINGLE `offers` tablename mapping (grep: one hit, line 24).
- Menu filter today is `grocer_id in selected` (menu.py:116) — the design's store clause
  extends exactly this line, no second filter mechanism.
- `upsert_week` keys on (grocer_id, external_id, week_key) (store.py:60) — design keeps
  this identity, store_id informational.
- Boot path is `Base.metadata.create_all` (database.py:58) — confirms the design's claim
  that a new column on the EXISTING offers table needs the guarded ALTER, which the
  design specifies.

## Architecture judgment
Reuse-first holds: one new package (`src/locator/`) for a genuinely new concern, every
shared mechanism (get_text, session injection, fail-tolerance, menu filter, profile row)
extended rather than duplicated; rejected alternatives named with reasons (§7). File
hygiene of the proposed tree: 8 new files, each single-concern, all far under the 250-line
target. Migration is minimal and reversible. Known limitations stated, not hidden (§9).

The devils-advocate gate for this design is a separate verifying phase (DA-verdict.md,
written by a devils-advocate child); this file records only the ARCHITECT closing judgment.

# VERDICT: PASS
