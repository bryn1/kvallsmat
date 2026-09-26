# PHASE-1 DEVILS-ADVOCATE GATE — matapp phase-0 bundlen (MC 1110 / kort 1110.4)

**Seat:** bernie (vm105) · **Datum (UTC):** 2026-09-07 · **Kort:** 1110.4 (PHASE-1 DA gate)
**Granskade deliverables (alla tre):**
- RESEARCH — `/srv/workspace/svarkor-matapp/PHASE0-research.md` (1110.1)
- ARCHITECTURE — `/srv/workspace/svarkor-matapp/PHASE0-map.md` (1110.2)
- PHASE PLAN — `/srv/workspace/svarkor-matapp/docs/PHASE0.md` (1110.3)

**Scope:** review only, ingen kod. Denna fil = den enda artefakten från detta kort.

# VERDICT: FIX

(→ FAIL. En namngiven closure-hål + en citerings-hygien defekt hittades i exakt de klasser
gaten är satt att fånga. Bundlen är i grunden sund — inga fabricerade källsökvägar, seams
håller — men två konkreta saker ges tillbaka till `[onfail:1110.3]` för reparation innan
SHIP. Se §2 och §3.)

---

## 1. Sammanfattning av granskningen

| Granskningspunkt (brief) | Resultat |
|---|---|
| (1) Spot-check citeringar för fabrication | **Ingen fabrication.** Alla bärande källsökvägar/URLer verifierade. 1 mindre citerings-hygien defekt (Crossref-query vs DOI). |
| (2) Closure-hål-prob (mbedtls/lwIP-klassen) | **1 realt closure-gap hittad:** `httpx` (feed-fetch-runtime-dep) är dev-only i POC `requirements.txt`, men varken kartans closure-tabell eller planens Phase 4 namnger att den måste in i deploy-requirements. |
| (3) Plan-följer-karta / karta-respekterar-forskning | **PASS.** 1:1 T→fas-mappning, `precedes:`-kanter = kartans beroendepil-uppsättning, closure-flaggor (argon2-cffi MISSING, referenspris-gap) korrekt nedärvda. |
| (4) Byggbar fas-journal | OK — fasplanen är byggbar, se §4. |

### Vad som verifierades denna exekvering (allt på vm105)

**POC-källsökvägar (13/13 PRESENT)** —`/srv/workspace/svarkor-matapp-root-route/dobbie/922.1-root-route-src-20260903/`:
`src/planner/menu.py`, `app/routers/menu.py`, `src/offers_db/store.py`, `src/recipes/store.py`,
`src/recipes/seed.py`, `src/fetcher/grocer.py`, `src/config.py`, `app/main.py`, `app/db.py`,
`server.py`, `static/js/utils/api.js`, `templates/index.html`, `app/models/store_selection.py`
— alla `PRESENT` (verifierat med `for f ...; if [ -e ]`).

**POC-kod-påståenden (VERIFIED):**
- greedy: `_offer_hit_count` (menu.py:93), `plan_menu(...)` (menu.py:141) ✓
- determinism: `seed` default `1234`, `rng = random.Random(seed)` (menu.py:142,158) ✓
- budget-tier: `pattern="^(budget|mid|premium)$"` (app/routers/menu.py:40) ✓
- Offer-schema: `class Offer(Base)` + `price_cents = Column(Integer)` (offers_db/store.py:17,25) ✓
- referenspris-gap: `grep -rIn "regular|original|was_price|ordinary|currentPrice|deletedPrice|regular_price" src/ app/` → **0 träffar** (gap bekräftat) ✓
- frontend: `const API_BASE = ''` (utils/api.js:12) ✓
- butiksval: `MAX_SELECTED = 3`, `store_ids[:MAX_SELECTED]` (app/models/store_selection.py:20,46) ✓
- ingest-linjen: `src/scheduler/periodic.py` + `src/normalizer/chain_mapper.py` PRESENT ✓

**Fleet prior art:** `/srv/workspace/svarkor-kvallsmat-recept/artemis/164.1-offers-machine-readable-20260820.md`
→ PRESENT (11470 bytes). ✓

**Externa URLer (curl):** Stigler diet Wikipedia → HTTP 200; arXiv 2501.04143 titel
`"Linear Optimization for the Perfect Meal..."` matchar citatet; OWASP Password Storage → 200
+ exakt text `"Use Argon2id with a minimum configuration of 19 MiB of memory, an iteration count
of 2, and 1 degree of parallelism"` matchar; OWASP Session Management → 200. ✓

**Willys live-claim (research Q4):** reproducibel `curl` gav exakt de citerade fälten
`comparePrice:"71,29 kr"`, `conditionLabel:"Spara 17,00 kr/st"`, `price.value:49.9` → VERIFIED. ✓

**Env-preflight (map §5):** python3 3.12.3, sqlite3 3.45.1 (stdlib), git 2.43.0, venv OK, pip3
→ alla som kartan säger. Motor-repo `/srv/workspace/svarkor-kvallsmat-recept-phase3-phase2/motor/src`
→ PRESENT. postpublish-accept.sh `/usr/local/bin/postpublish-accept.sh` → PRESENT
(`-rwxr-xr-x 1 root root 24055`). ✓

---

## 2. NAMNGIVEN REPARATION (vad `[onfail:1110.3]` måste laga)

### FIX-1 — Closure-hål: fetch-runtime-dep `httpx` måste synkas in i deploy-requirements (map §4 + plan Phase 4)

- **Bevis (denna exekvering):** POC `/srv/workspace/.../922.1-root-route-src-20260903/requirements.txt`
  innehåller ENDAST: `fastapi==0.141.1 uvicorn==0.52.4 sqlalchemy==2.0.52 pydantic==2.13.4` — och
  kommentaren säger rakt ut *"the test-only deps (pytest, httpx) are NOT shipped."* Samtidigt
  `import httpx` finns i `src/fetcher/grocer.py:19`, och ingest-linjen (scheduler→fetcher→aggregate→
  normalizer→upsert) är en *runtime*-funktion i den framtida maten (kartan visar den i flödet).
- **Hålet:** kartans closure-tabell raderar `httpx` som `PRESENT` med noten "dev/test" — korrekt men
  ofullständigt: den höjer inte upp **"flytta fetch-runtime-dep(er) till produktions-requirements"**
  som en namngiven closure-gap, och planens Phase 4 (T3) gör bara mock-driven DoD
  (`regular_price_cents > price_cents` på inspelad feed) — den testar alltså **INTE** att
  fetch-sökvägens HTTP-klient är närvarande i deploy-venv:et. En byggare som följer planen kan
  passera Phase 4 och ändå deploya en ingest som inte kan hämta feeds live.
- **Åtgärd (kartans §4 closure-gap-lista + plan Phase 4):** lägg till namngiven gap-rad —
  *"`httpx` (feed-fetch) måste läggas till produktions-`requirements.txt` med pin, eller besluta att
  ingest körs som fristående offline-jobb utanför vm106-webbtjänsten (då: dokumentera det som
  Phase 4 OPS-antagande)"* — och lägg en Phase 4-DoD-bar som bekräftar att fetch-path-deps finns i
  den deployade runtime-miljön (inte enbart mock-motstånd).

### FIX-2 — Citerings-hygien: Crossref "Smart Grocery Shopping" ska citera DOI, inte query-URL (research Q1)

- **Bevis (denna exekvering):** DOI `10.1109/smc58881.2025.11343611` **resolverar korrekt** till det
  citerade pappret: *"Smart Grocery Shopping: a Utility-Based Mathematical Framework and Optimal
  Strategies"*, container `2025 IEEE International Conference on Systems, Man, and Cybernetics (SMC)`,
  publisher IEEE → pappret är **REALT, ej fabricerat**. Men den citerade *Källan*
  (`https://api.crossref.org/works?query.bibliographic=Smart+Grocery+Shopping`) returnerar
  **inte** pappret bland toppträffarna (626 256 resultat, pappret inte i topp ~12) — en läsare som
  följer den URL:en hittar inte källan.
- **Åtgärd:** i research-Q1, byt Källan till direkt-DOI `https://doi.org/10.1109/smc58881.2025.11343611`
  (eller slash-formen). Behåll PLAUSIBLE-UNCHECKED-märkningen (abstrakt ej hämtat).

---

## 3. Inte blockerande, men registerförs som DA-noteringar

- **validate-hosting.py (Phase 9 ship-gate-bar) är INTE närvarande på vm105** — `find / ... name
  validate-hosting.py` och `repo-visibility-hosting`-mappen → 0 träffar. Planen markerar själv detta
  ärligt som *"UNVERIFIED-on-this-host; Phase 9 verifierar den på bygg-rotens faktiska väg"*. Att skjuta
  verifieringen till buildfasen är acceptabelt, MEN Phase 9:s DoD-bar är därmed en **forward-referens
  till en bar vars existens på målmiljön inte är bevisad**. Phase 9 måste bekräfta `validate-hosting.py`
  faktiskt finns på bygg-roten innan den kör baren, annars rapportera UNVERIFIED, aldrig PASS.
- **ica/coop token (Phase 4):** korrekt flaggad PLAUSIBLE-UNCHECKED; om de inte nås utan nycklar ska
  majoritet-mätning begränsas till willys (öppen) och rapporteras UNVERIFIED-REQUIRES-FEED. Planen
  hanterar detta korrekt i PH6.

---

## 4. Journal-resonera en byggbar fas (gate task 4)

Fasplanen (Phase 2..10, T1–T9) är **byggbar och konsistent** med kartan:

- **1:1 T→fas:** T1→Ph2, T2→Ph3, T3→Ph4, T4→Ph5, T5→Ph6, T6→Ph7, T7→Ph8, T8→Ph9, T9→Ph10. ✓
- **Dependency-kanter (precedes) = kartans beroendepil-uppsättning:** verifierade rad-för-rad —
  T5/T6 kräver T1,T3 resp. T2,T4,T5; Ph2→Ph3∥Ph4 parallella grenar möts vid Ph6 (T5) och Ph7 (T6) —
  identiskt med kartans §3 exekveringsordning 1..7. ✓
- **seat + gate + onfail + cycles per fas:** alla närvarande — seat: backend=bernie, frontend=frontend,
  hosting/post-publish=henrik; gate=C1..C9 (dobbie); onfail=fasen själv; cycles=2..4. ✓
- **UNVERIFIED ≠ PASS:** planens PH4/PH6-krav gör det explicit (inga faser påstår produktionsklarhet
  bortom evidens; env-dep ej verifierad = UNVERIFIED, aldrig PASS). ✓
- **Hosting/post-publish DoD:** BÅDA web-hosting-itemen bärs — DoD1 (hosting.yaml + `0.0.0.0:$PORT`,
  bar `validate-hosting.py ; exit 0`) på Phase 9, DoD2 (post-publish-accept, bar
  `postpublish-accept.sh --url https://sibbamala.com/matapp/ ...`) på Phase 10, routad till henrik
  (enda vm105-seat med browser+vision). Ingen skip. ✓ Way: appen är en hosted web-app, så båda krävs.
- **Harness self-test (kan fela):** PH4 kräver tvåsidig kalibrering — grönt körfall + avsiktligt
  rött brytfall per fas-gate (auth utan argon2-pin, normalizer utan referenspris, /api/profile utan
  auth, optimizer med tröskel 0.0…). Rätt anti-false-green-struktur. ✓
- **Evidence-paths = workspace, aldrig /tmp.** ✓

Netto: själva *fasformen* är sund och byggbar — därav FIX, inte RECONSIDER. Bara de två namngivna
sakerna (§2) repareras i bundlen.

---

## 5. Verifieringsnivåer

- Allt i §1 är **VERIFIED** = kommando/curl/läs kört denna exekvering på vm105 (paths + utdrag ovan).
- **ASSUMED** = inga; alla slutsatser bär live-bevis.
- **BLOCKED** = ingen blockerare; varje påstående i denna fil kunde instrumenteras.

VERIFY_EXIT=0
