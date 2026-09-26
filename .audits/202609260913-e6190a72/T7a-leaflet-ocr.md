# T7a — Can OCR/image analysis of weekly leaflets (veckoblad) be the offer source for Willys and Coop?

MC card 1355.8 (parent 1355) · matapp offer-source research · 2026-09-26
Note on placement: the workspace was reorganized to layout v2 mid-run; the deliverable lives at `/srv/workspace/matapp/.audits/202609260913-e6190a72/T7a-leaflet-ocr.md` (the task's original `/srv/workspace/svarkor-matapp-audit-2026/` path no longer exists). The prior T2 doc is archived at `/srv/workspace/matapp/.audits/legacy-audit-2026/T2-data-sources.md` and was read this session.

## Headline finding (changes the question)

**Both Willys and Coop publish their weekly leaflets through Tjek (tjek.com, formerly ShopGun), and Tjek's public "squid" API serves the leaflet's offers as STRUCTURED JSON — product name, price, unit, validity dates — with no authentication.** OCR is therefore not needed for either grocer: the leaflet provider itself is a better offer source than OCR of the leaflet images.

- VERIFIED: `https://squid-api.tjek.com/v2/catalogs/8TeMm7nX` (Stora Coop Västberga, week 2026-09-21→27) returns JSON with `page_count: 16, offer_count: 109`, `run_from`/`run_till` — fetched directly this session, HTTP 200.
- VERIFIED: `https://squid-api.tjek.com/v2/catalogs/8TeMm7nX/hotspots` returns per-offer records: `{"type":"offer","heading":"Bryggkaffe","offer":{"pricing":{"price":109,"currency":"SEK"},"quantity":{"unit":{"symbol":"g","si":{"symbol":"kg","factor":0.001}},"size":{"from":450,"to":500}},"run_from":"2026-09-20T22:00:00+0000","run_till":"2026-09-27T21:59:59+0000"}}` — name, price, unit, size range and validity in one record.
- VERIFIED: same for Willys: `/v2/catalogs/wRVvbIj1` (Willys Stockholm Mariahallen, 12 pages, 111 offers) and `/v2/catalogs/wRVvbIj1/hotspots` (e.g. `GOUDA`, 49.9 SEK, kg, valid to 2026-09-27).
- VERIFIED: dealer-level listing works without knowing publication ids: `/v2/catalogs?dealer_id=c371GA` (Willys) and `?dealer_id=6c28SD` (Stora Coop) each return the full set of per-store leaflets (24 for Stora Coop).
- VERIFIED: `api.tjek.com` does not resolve publicly (NXDOMAIN via dns.google and local resolver); the working host is `squid-api.tjek.com` (found in the ereklamblad.se JS bundle: `https://squid-api.tjek.com` with an `apiUrl`/`apiKey` config block).
- VERIFIED: ereklamblad.se (Aller/Tjek consumer front-end) embeds per-business `app-data` JSON naming the dealer publicIds: Willys `c371GA`, Stora Coop `6c28SD`, with publication ids and validity windows.

## 1. Willys

**Leaflet existence and format**
- VERIFIED: Willys' own site has no reachable veckoblad page: `https://www.willys.se/veckoblad` → 404, `/veckobladet` → 404, `/kampanj` → 404 (fetched this session). `/erbjudanden` (HTTP 200) contains no leaflet iframe/PDF link and no reference to any leaflet provider (grepped for ipaper/bluestep/aptoma/pressify/veckoblad/pdf — zero hits).
- VERIFIED: the Willys leaflet exists as page images on Tjek: `https://ereklamblad.se/Willys` (HTTP 200) embeds dealer `c371GA` and publication `wRVvbIj1` ("Willys Stockholm Mariahallen", valid 2026-09-21→27). Pages are raster images: `/v2/catalogs/wRVvbIj1/pages` returns signed `image-transformer-api.tjek.com` URLs; downloading the `zoom` URL returned a **1400×2022 JPEG** (HTTP 200, `image/jpeg`, ~464 KB). No PDF is served by this pipeline — the leaflet is image-only.
- UNVERIFIED: whether Willys offers any official PDF download anywhere (none found via site probes or search; absence claim is bounded by the probes run).

**Is OCR viable?**
- Technically yes but strictly worse than the alternative. The pages are clean, high-resolution (1400 px wide at `zoom` tier; the image-transformer accepts a `w` parameter, larger sizes likely available) print renders, so Tesseract (`tesseract -l swe`) on the JPEGs would read most prices. Tooling: stdlib-first `urllib`/`requests` for download, `pdfminer`/`pypdf` are irrelevant (no PDF — there is no text layer to extract), so raster OCR via `tesseract` (or `pytesseract`) is the only path.
- Failure modes (INFERRED from the layout seen in the hotspots' bounding boxes and typical leaflet design): multi-column layouts scramble reading order; price/unit pairs ("49:90/kg", "3 för 2", "Jämförpris") need Swedish-specific parsing; member-price vs regular-price badges; per-store leaflets (Willys publishes one per store — dealer c371GA lists many) multiply parsing volume; weekly layout redesigns silently break parsers.
- Maintenance burden: HIGH — every layout change can break extraction, and accuracy must be re-validated weekly. This is the classic last-resort profile.

**Comparison against the T2 alternatives**
- T2 alternative (VERIFIED via archived T2, lines 39–58): Willys runs SAP Commerce Cloud (OCC); the exact working OCC search/campaign endpoint is UNVERIFIED there and needs a browser devtools session — the SPA calls it client-side and simple URL probing 404s.
- NEW, better than both: the Tjek squid API gives structured offers for Willys with one GET per store leaflet, no auth observed, no OCR, no browser automation. **OCR is a last resort for Willys; the Tjek API is the easiest path.**

**ToS/robots**
- VERIFIED: `https://ereklamblad.se/robots.txt` returns the SPA HTML shell (HTTP 200, HTML not a robots file) — no robots rules observed; `squid-api.tjek.com/robots.txt` → 404 "Not Found". Absence of robots.txt means no crawl restrictions declared via robots, but this is not a ToS clearance: Tjek's API terms were not reviewed (UNVERIFIED). The API is the same unauthenticated one the consumer app/ereklamblad uses; treat rate limits as unknown and cache weekly.

**Feasibility verdict: OCR = viable-but-last-resort. Recommended source = Tjek squid API (`/v2/catalogs?dealer_id=c371GA` → `/v2/catalogs/{id}/hotspots`).**

## 2. Coop

**Leaflet existence and format**
- VERIFIED: `https://www.coop.se/erbjudanden/veckoblad/` exists (HTTP 200 after redirect to the SPA shell) but serves no leaflet markup server-side — the page is a JS shell; grepping it for ipaper/bluestep/aptoma/pressify/pdf found nothing.
- VERIFIED: the Coop leaflet is on Tjek: `https://ereklamblad.se/Stora-Coop` (HTTP 200) embeds dealer `6c28SD` with two live publications (e.g. `8TeMm7nX`, "Stora Coop Västberga", valid 2026-09-20→27, 16 pages, 109 offers). Same image-only pipeline as Willys (signed webp/JPEG page images, no PDF).
- VERIFIED: Coop's own APIM gateway paths are visible in the coop.se page source: `https://external.api.coop.se/dke/offers/`, `/articleservice`, `/digital/...`, plus `proxy.api.coop.se/external/...` — matching archived T2 lines 62–76 (`dkeUrl` with its own `dkeKey`, `hybrisApiUrl: https://external.api.coop.se/ecommerce`). Probing `external.api.coop.se/dke/offers/` and `/articleservice` directly returned `404 {"statusCode":404,"message":"Resource not found"}` — the paths exist but need query params/auth not captured from static HTML; T2's conclusion (real paths need a devtools capture of handla.coop.se traffic) stands.

**Is OCR viable?**
- Same assessment as Willys: technically feasible on clean 1400-px JPEG page renders with Tesseract `swe`, but with the same failure modes (multi-column, jämförpris, member prices, 24 per-store leaflets for Stora Coop alone, weekly layout drift). Maintenance burden HIGH.

**Comparison against the T2 alternatives**
- Tjek squid API again beats both alternatives: `/v2/catalogs?dealer_id=6c28SD` → `/hotspots` gives structured offers with no auth. The Coop APIM path (`/dke/offers/` with `dkeKey`) remains worth one devtools capture session (it likely gives store-scoped, member-priced data), but it is no longer the only non-OCR option.
- **OCR is a last resort for Coop; the Tjek API is the easiest path, with the APIM capture as the higher-fidelity follow-up.**

**ToS/robots**
- Same as Willys: no robots rules observed on ereklamblad.se (SPA shell served for /robots.txt), squid-api robots 404. Tjek API terms UNVERIFIED. coop.se itself is a normal commercial site; no robots.txt review of coop.se was needed since the recommended path does not scrape coop.se.

**Feasibility verdict: OCR = viable-but-last-resort. Recommended source = Tjek squid API (`/v2/catalogs?dealer_id=6c28SD` → `/hotspots`); APIM `/dke/offers/` capture as a P2 improvement.**

## 3. ICA and Lidl (brief, for comparison)

- UNVERIFIED-HERE beyond the archived T2 (which documents ICA page-embedded JSON and Lidl campaign-page JSON as working): neither ICA nor Lidl appears on ereklamblad under the obvious slugs — VERIFIED `ereklamblad.se/ICA` → 404 (note `ereklamblad.se/ICA-Supermarket` returned 200 — an unrelated business entry, not ICA's national leaflet pipeline; not investigated further). No change recommended for ICA/Lidl; the Tjek pattern is only relevant where a grocer has no direct JSON.

## 4. Tooling summary (if OCR is ever needed)

- No PDF exists for Willys/Coop leaflets on the Tjek pipeline → `pdfminer`/`pypdf` text-layer extraction is NOT applicable (INFERRED from the pages endpoint serving only raster images; VERIFIED that the `pages` endpoint returns image URLs only).
- Raster path: download signed page JPEGs (`urllib`, stdlib) → `tesseract -l swe --psm 6` (or `pytesseract`) → regex parse price/unit/validity. Expect to need per-chain layout templates and weekly validation; budget it as the maintenance-heaviest option and only as a fallback if the Tjek API is withdrawn.

## Per-claim index

| Claim | Level |
|---|---|
| willys.se/veckoblad & related paths 404; no leaflet provider on willys.se | VERIFIED |
| Willys + Coop leaflets hosted on Tjek via ereklamblad.se (dealer ids c371GA / 6c28SD) | VERIFIED |
| squid-api.tjek.com/v2/catalogs/{id} + /hotspots return structured offers, no auth | VERIFIED |
| /v2/catalogs?dealer_id= lists all per-store leaflets | VERIFIED |
| Leaflet pages are raster JPEG/webp, no PDF, no text layer | VERIFIED (pages endpoint + downloaded image) |
| api.tjek.com NXDOMAIN; squid-api is the live host | VERIFIED |
| Coop APIM bare paths /dke/offers/, /articleservice 404 without params/auth | VERIFIED |
| T2 findings (ICA page JSON, Lidl campaign JSON, Willys OCC unreachable) | VERIFIED via archived T2 (read this session) |
| Tjek API terms of service permit this use | UNVERIFIED |
| OCR accuracy figures for Swedish grocery leaflets | INFERRED (no benchmark run) |

# VERDICT: PASS
