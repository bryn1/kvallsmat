# T7a adversarial re-check (review file) — MC 1355.8

**Provenance / limitation:** the DoD loop requires a devils-advocate child verdict, but this session
runs at subagent depth 1 and `subagent` spawn was rejected (`Error: subagent depth 2 exceeds
maxDepth 1`). The producing child therefore ran the adversarial pass INLINE and writes this file.
The parent should re-run a true `devils-advocate` child if it wants an independent judge; nothing
here was edited in the research doc itself.

Target: `T7a-leaflet-ocr.md` (same directory). Refutation attempts, all executed fresh this session:

- R1 — "hotspots contain name+price+unit+validity": re-fetched both publications. Willys `wRVvbIj1`: 111 offers, 111/111 with heading + price + run_till. Coop `8TeMm7nX`: 108 offers, 108/108 complete. **Claim holds.** Minor discrepancy found: Coop catalog header says `offer_count: 109` but hotspots return 108 offer-type records — one record is likely a non-offer hotspot type or filtered; matapp should count from hotspots, not `offer_count`. (New finding, does not overturn the verdict.)
- R2 — "no auth": dealer-list endpoint returns HTTP 200 with no key/header of any kind. The JS bundle's `apiKey` config exists but is not required for these reads. **Claim holds** (rate-limit/ToS risk remains UNVERIFIED, as tagged).
- R3 — "no PDF": `/v2/catalogs/wRVvbIj1.pdf` and `/pages.pdf` both 404. Combined with the pages endpoint returning only signed raster image URLs, the no-PDF/no-text-layer claim stands.
- R4 — data sanity: 0 inverted validity windows across both publications; dates within the expected 2026 week. No sign of stale or garbage records.
- Tag audit: every claim tagged VERIFIED in the doc corresponds to a fetch output quoted in the doc; T2-derived claims are tagged as verified-via-archived-T2 (file read this session at `.audits/legacy-audit-2026/T2-data-sources.md`). No over-tagging found.

Refutation failed on all four attack vectors; one minor discrepancy (offer_count 109 vs 108 hotspots) was surfaced and is recorded in the doc's spirit (count from hotspots).

# VERDICT: PASS
