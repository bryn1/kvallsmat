# MC 1188 — matapp full audit: SYNTHESIS (goal vs current state)

Parent 1188, children 1188.1 (verified), 1188.5, 1188.9, 1188.10 (completed_unverified,
evidence on disk). All reports in /srv/workspace/svarkor-matapp/audit/. Synthesized by
svarkor 2026-09-13. Every claim below is VERIFIED in a child report unless marked.

## Goal-diff (PHASE0-map §1) — headline

LIVE = POC (12e2e30). Framtidsversion 4d220cd built but NOT live (publish gave 502, reverted).

| Måldel | Live | 4d220cd |
|---|---|---|
| 1 Auth argon2id+session | saknas | byggd, ej live |
| 2 Profil (3 butiker, kron-budget, personer, måltider) | saknas | byggd, ej live |
| 3 Tre veckomenyförslag | saknas (1 plan) | byggd, ej live |
| 4 Majoritet extrapris (ratio ≥50%, referenspris) | saknas | DELVIS — ratio-filter + kolumner finns men optimeraren äter HÅRDKODAD fixture (12 offers willys W37); riktig ingest-linje saknar referenspris i BÅDA versioner |
| 5 Reklamblad per butik | strukturellt (store-select 200) men funktionellt dött — alla used_offer_ids tomma | ingest-linje oförändrad |

## Top findings across the three gates

SECURITY (1188.9, henrik):
- F1 HIGH: 4d220cd server.py sätter KVALLSMATS_DB_URL men database.py läser MATAPP_DB_URL
  — state-dir-override död; deploy av auth-versionen kraschar på boot (empiriskt verifierat).
- F2 HIGH: ingen rate-limit/lockout på login (50 bad logins, ingen låsning).
- F3 MEDIUM: username-enumeration via timing (37 ms vs 2 ms).
- F4 MEDIUM: sessions in-memory utan TTL.
- F5 MEDIUM: PUT /api/profile validerar inte selected_stores mot katalogen.
- F6-F8 LOW: innerHTML-sinks (dish_id/store.name), kron_budget<0 → 500, ingen CSP/SRI.
- F9-F12 INFO: ingen demo_guard/per-visitor rate-limit på POST /select; fetcher utan timeout;
  DB 0644; stray --help/-katalog.
- NOT findings: POC open-login = by design (owner ruling); ingen SQLi/shell-injection/path
  traversal/secrets; cookie-attribut korrekta; 401 aldrig 200 på skyddade routes.

CORRECTNESS (1188.10, gunilla):
- Suite: 68/68 green, färsk körning, VERIFY_EXIT=0.
- BUG-1: week 9999-W99/0000-W01 → OverflowError → 500.
- BUG-2: icke-existerande veckonummer (W54, W00) accepteras tyst → fel datum.
- BUG-3: DB-parent-dir saknas → boot-crash (mitigerat i prod av STATE_DIRECTORY makedirs).
- BUG-4: allergens-param tyst bortkastad (frontend skickar, backend tar aldrig emot).
- Dead code: 2 döda konstanter, 1 oåtkomlig gren, 1 oanvänd helper; scraper/ingest owired.

VISION CLICK-THROUGH (1188.5, bernie):
- Console rent vid load, alla 12 klick OK, inga döda länkar, alla assets 200.
- F1 MEDIUM: 422-felmeddelanden visas som generisk text — err.detail läses aldrig i UI.
- F2 LOW: zero-offer-badge kontrast 4.26:1 (< AA 4.5:1).
- F3 LOW: 320px overflow (360px spec-bredd är ren).
- F4-F7 LOW/INFO: allergens ej validerade server-side; meny genereras utan butiker valda;
  W0/W99 accepteras; --color-success-700-token saknas.
- Caveat: vision_analyze timeout 7/7 — pixel/overflow-analys + WCAG-matte ersatte ögonpasset;
  8 screenshots sparade för mänsklig granskning.

## Decision list for the owner (rec per item)

1. REC: fixa F1 (env-var-mismatch) + BUG-1/BUG-2 (week-validering) i 4d220cd INNAN nästa
   publiceringsförsök — F1 ensam skulle reproducera 502/kraschen.
2. REC: lägg rate-limit/lockout (F2) + timing-jämnare login (F3) i samma fixrunda.
3. REC: besluta referenspris-genomströmning i riktig ingest (måldel 4) — största kvarvarande
   gapet mot målet, finns inte ens i 4d220cd.
4. REC: låt live POC stå kvar tills fixrundan är klar (open-login by design, inga P0:or live).
5. ÖPPEN: ica/coop feed-funktion förblir overifierad (token-gated) — owner-only steg.

VERIFY_EXIT=0
