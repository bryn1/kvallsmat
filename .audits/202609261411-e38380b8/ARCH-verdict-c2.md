# ARCH-verdict-c2 — T10b design Revision 2 (store-level selection per postnummer), MC 1355.13

Written by the design (arch) child, cycle 2 (back-edge after DA cycle 1 returned FIX),
2026-09-26. Judged artifact: `/srv/workspace/matapp/.audits/202609260913-e6190a72/T10b-design.md`
Revision 2 (copy in this out dir). Supersedes ARCH-verdict.md (cycle 1) — that file is
left untouched; this newest file decides.

## DA findings — disposition (all addressed, none rejected)
Checked each finding in `/srv/workspace/matapp/.audits/202609260913-e6190a72/T10c-da-verdict.md`
against the revised design text:
- P0 upsert retraction → §3 now prefixes store-scoped external ids AND scopes the
  `upsert_week` match key with `store_id or ""`; NULL rows can never be overwritten.
  The retracted "collisions not expected" claim is gone.
- P1 filter double-count → §4 dedup step `(grocer_id, normalized name)`, store-level
  preferred.
- P1 profile migration → §3 guarded ALTERs for ALL THREE columns; the contradictory
  parenthetical deleted.
- P1 Coop circularity → §2 daily persisted all-787 detail cache; cold-start cost stated.
- P1 unauthenticated amplification → §4 `?postal_code=` auth-gated (401 anonymous) +
  caches.
- P2 absent-means-unchanged, P2 status/resolved_at/TTL, P2 duplicate-column tolerance,
  P3 coop key runtime fetch + Willys flyerURL join → all in §2/§3/§4/§5, mapped in §10.

## Decisive checks re-run by this child this session (evidence)
- `tail -1 T10b-design.md` → `# VERDICT: SHIP`; `grep -c "Revision 2 (DA cycle 1)"` → 1.
- P0 fix present: match key `(grocer_id, external_id, week_key, store_id or "")` (line 90)
  and prefixed external id `f"{store_id}:{hotspot_id}"` (lines 94/117).
- "guarded ALTERs at boot for ALL THREE new columns" present (line 103).
- Dedup + auth-gate language present (lines 135/162 and §4 stores row).
- Revised doc is 267 lines, one subject, sections intact (module table, endpoints, schema
  + migration, data flow, UI, rejected alternatives, offline tests, limitations, revision
  log). Out-dir copy synced byte-identical (`cp` + diff-by-content this session).

## Architecture judgment
The revision keeps the cycle-1 architecture (resolve-once, one locator package, no new
endpoint family) and repairs the data-integrity and security seams the DA proved. The
P0 fix uses the upsert match key + id prefixing rather than a constraint change — the
only SQLite-viable shape. Reuse-first and file hygiene still hold.

Note: the DA's re-verdict on Revision 2 (a new DA file, e.g. DA-verdict-c2) is a separate
verifying phase owned by the orchestrator; this file records only the ARCHITECT closing
judgment on the revised design.

# VERDICT: PASS
