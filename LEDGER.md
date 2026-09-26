# LEDGER — Matapp (github.com/svarkor-ai/Matapp)

Grocery menu planner: ingests weekly offers from Swedish grocers, plans menus from
recipes against those offers. FastAPI app (`app/`) + ingest motor (`src/`).

STATUS: ACTIVE — audit + real-offers build landed 2026-09-24 (MC 1355).

## Dated entries
- 2026-09-24 (MC 1355.1, T1 audit): fresh suite 9 passed; findings P0×2 (no store-selection
  in source; two-way source/hosting divergence), P1×3 (canned menu data, profile accepted
  unknown/duplicate stores, mock-only motor), P2×4, P3×2. Artifact audit/T1-correctness.md.
- 2026-09-24 (MC 1355.2, T2 research): real offer data sources mapped. ICA erbjudanden page
  embeds complete weeklyOffers JSON server-side; Lidl campaign pages embed product JSON with
  deletedPrice; Coop has a real APIM gateway (paths need devtools capture); Willys OCC not
  URL-reachable. Ranking ICA > Lidl > Coop > Willys. Artifact audit/T2-data-sources.md.
- 2026-09-24 (MC 1355.3, T3 port-back, commit 5f3bc1d): stores router + config seam ported
  from the deployed copy into the source; profile store validation 422s unknown/duplicates.
- 2026-09-24 (MC 1355.4, T4a, commit 49f0914): real ICA+Lidl fetcher adapters behind the
  existing RawFeed contract (fail-tolerant); Lidl added to CHAIN_MAP + default catalog.
  Live sanity: ICA 11 entries, Lidl 132 entries parsed.
- 2026-09-24 (MC 1355.5, T4b, commit b06c309): /api/menu takes a validated week param
  (422 on impossible weeks — kills latent BUG-1/BUG-2); menu planned from offers-DB rows
  filtered to selected stores; boot-time ingest in lifespan; shared week-math helper
  src/planner/weeks.py (dedup).
- 2026-09-24 (MC 1355.6, T5 DA gate): VERDICT FIX — P1 silent total failure, P1 extrapris
  rule dead (no regular prices), P1 no user provisioning, P2 double prefix. Artifact
  audit/T5-DA-verdict.md.
- 2026-09-24 (MC 1355.7, T6 fixround, commits 77ff2ad + 966ddaa): /health offers signal +
  0-entry grocer warnings; Lidl deletedPrice → regular_price_cents (andel_extrapris now
  non-zero, 0.333 observed); single-prefix external ids; POST /api/auth/register
  (owner-ratified open registration). Suite 53 passed EXIT=0.
- 2026-09-24 (orchestrator e2e verification): boot → real ingest (71 offers: ica 11,
  lidl 60) → register → select ica+lidl → menu 2026-W39 with 9/15 days carrying real
  used_offer_ids. VERIFIED.

## Known limitations / open items
- Willys + Coop still serve 0 real offers (willys needs a devtools OCC capture; coop needs
  real APIM resource paths — see T2 §2/§3). They warn in logs and count 0 in /health.
- Ingest runs at boot only; no periodic refresh yet (later card).
- Menus for non-current weeks degrade to recipe-only (ingest writes the current week).
- Deployed copy /srv/workspace/hosting/apps/matapp is now BEHIND the source repo; deploy
  pending owner go.
- 2026-09-26 (MC 1355.8/1355.9, T7 research): OCR of veckoblad = last resort only; Willys+Coop
  offers wireable via Tjek squid API (dealer c371GA / 6c28SD, hotspots = structured JSON, no
  auth). Offers are STORE-GATED for ICA/Willys/Coop (ICA merchant-priced by design; Willys
  "från respektive butik"; Coop helpcenter confirms store variation); Lidl national (single
  region in regionsPrices). Per-store cart needs store-level data for 3 of 4 chains.
- 2026-09-26 (MC 1355.10, T8, commit c16d088): Tjek adapter wired for willys+coop behind the
  existing RawFeed contract. Live pull all four: willys 111, ica 11, coop 97, lidl 132 real
  offers. Orchestrator e2e: health offers_current_week=279; register→profile(willys,ica,lidl)
  →menu 2026-W39 with 15/15 days carrying real used_offer_ids, max andel_extrapris 0.333.
