# PHASE 4 (T3) offer-ingest-referenspris — BUILD EVIDENCE (kort 1143.4)

**Seat:** bernie · **Datum (UTC):** 2026-09-08 · **Kort:** 1143.4 (Phase 4 T3 offer-ingest; parent 1143)
**Deliverable (source-only tree):** `/srv/workspace/svarkor-matapp/bernie/1143.4-offer-ingest-referenspris-20260908/`
**Gränssnitt mot gate C3 (dobbie):** denna fil = byggarens evidens; C3 graderar till
`# VERDICT:` PASS/FAIL enligt `/srv/workspace/svarkor-matapp/briefs/gate-p4.txt`
(ingest-harness mock willys → regular > price; trasig normalizer RÖD; `grep -qE '^httpx=='` exit 0).

# VERDICT: PASS (builder-side; await C3 grader)

> Byggaren deklarerar sig klar och hela Phase 4-DoD är kört med grönt resultat på det
> publicerade trädet (se §3 exekverad output). C3 (dobbie) sätter slutgiltig VERDICT-rad
> i sin egen gate-evidence.

---

## 1. Vad byggdes (closure av Phase 4-krav, PHASE0.md §P Phase 4 / PHASE0-map §6 T3)

| Krav (gate C3) | Leverans |
|---|---|
| RawOffer→NormalizedOffer→Offer bär `regular_price_cents`/`savings` (Willys bär båda — closure-gap 1) | `app/ingest/grocer.py` (RawOffer bär `regular_price_cents`, parsat från willys `comparePrice` "71,29 kr"→7129, fallback `lowestHistoricalPrice.value`); `app/ingest/normalizer.py` (→NormalizedOffer med `regular_price_cents`/`savings_cents`); `app/ingest/ingest.py` (persist till `app.models.offers_db.Offer`, samma offers-tabell Phase 2 deklarerade) |
| Per-ingrediens-extrapris-flagga i normaliseringssteget (ej i DB — map öppna fråga 2, line 224) | `app/ingest/normalizer.py` — `is_extraprice = regular_price_cents is not None and regular_price_cents > price_cents`, beräknad i normaliseringssteget, ej lagrad i DB |
| HAL-seam: host-mock = injicerad httpx-lik `session` | `pull_grocer(grocer_cfg, week_key, session=None)` (POC-seam behållen); `app/ingest/willys_mock.py` = injicerad `session` som serverar inspelad willys-feed (VERIFIED live-struktur 1110.1 Q4) |
| DoD: ingest-harness mot inspelad willys-feed mock producerar Offer-rad med `regular_price_cents > price_cents` (exit 0) | `harness_ingest.py` GREEN case — se §3 |
| DoD: trasig normalizer (utan referenspris) RÖD | `harness_ingest.py` RED case — `broken_normalizer_drops_reference`, se §3 |
| **DA FIX-1:** `grep -qE '^httpx==' requirements.txt` exit 0 | `requirements.txt` — `httpx==0.28.1` pin (runtime-dep, ej dev-only; offline-ingest-alternativet förkastat — gaten kräver att httpx-runtime-dep finns) |
| Ingen ny dep utöver pin (greedy/återbruk) | endast httpx tillagd; sqlalchemy/fastapi/uvicorn/pydantic ärvda från Phase 2-trädet |

## 2. Lingval & designnot (kod-disciplin)
Repo är helt Python (FastAPI/SQLAlchemy) — Python är rätt verktyg här, ingen port till Rust
(glue/persistence på befintlig stack; coding-discipline §Language-preference undantag).
Kodfilerna målade under ~150 rader, en concern per modul; POC-modulerna (fetcher/normalizer)
EXTENDERAS inte utan återskapas i `app/ingest/*` på samma CONTRACT-shape (återbruk av mönster,
inte byte kopia) och integreras med Phase 2:s `app`-paket + shared `database.Base`.

## 3. DoD — exekverad på det publicerade trädet (pinned runtime venv ~/p4-venv)

Runtime: `~/p4-venv/bin/python3` med `sqlalchemy==2.0.52` + `httpx==0.28.1` (VERIFIED install).

### CHECK 1 — ingest-harness mot inspelad willys-feed mock → Offer med regular > price (exit 0)
```
$ cd /srv/workspace/svarkor-matapp/bernie/1143.4-offer-ingest-referenspris-20260908
$ ~/p4-venv/bin/python3 harness_ingest.py
== GREEN CASE: ingest willys mock -> reference price on Offer row ==
[ok] parse_swedish_kr('71,29 kr') == 7129 (got 7129)
[ok] ingest wrote >=1 Offer rows (wrote 3)
[ok] all 3 in-week entries normalized (got 3)
[ok] extrapris flag fired on >=2 offers (got 2)
[ok] >=1 Offer row persisted for the week
[ok] >=1 stored Offer with regular_price_cents > price_cents
[ok] w37-0001 regular_price_cents == 7129 (comparePrice '71,29 kr' parsed + persisted)
[ok] w37-0001 savings_cents == regular - price
[ok] max reference-price row is the big-discount item (got w37-0001)
[GREEN] written=3 normalized=3 extraprice_count=2
[GREEN] sample stored rows:
    w37-0001: price=4990 regular=7129 savings=2139
    w37-0002: price=1990 regular=2990 savings=1000
    w37-0003: price=3990 regular=3500 savings=0
GREEN-CASE-EXIT=0

== RED CASE: broken normalizer (no reference price) must go RED ==
[RED] broken normalizer dropped the reference price; pipeline correctly FAILED
[RED] written=3 extraprice_count=0 (expected 0 extraprice flags)
RED-CASE-EXIT=1  (expected non-zero — anti-false-green calibration tripped)

HARNESS RESULT: PASS (green DoD + anti-false-green red trip)
HARNESS_EXIT=0
```
`HARNESS_EXIT=0`. Direkt DB-bevis: lagrad `w37-0001` har `regular_price_cents=7129 > price_cents=4990`
(kvarg vanilj; willys `comparePrice:"71,29 kr"` parsat→7129). Per-ingrediens-flaggan betedde sig
konsekvent: 2/3 erbjudanden är extrapris; `w37-0003` (referens 3500 < pris 3990) är INTE — strikt
regel `regular > price` håller. Red-case bekräftar anti-false-green: en normalizer som tappar
referenspriset ger `extraprice_count=0`, ingen rad har referenspris → gaten föll som den ska.

### CHECK 2 — trasig normalizer (utan referenspris) gick RÖD
Red-casen ovan (`RED-CASE-EXIT=1` i CHECK 1) är den avsiktligt trasiga variantsn som måste gå
RÖTT; harnessens egen assertion `regular_hits >= 1` misslyckades → `AssertionError` → exit≠0.
HARNESS_RESULT=PASS betyder BÅDE green-DoD och red-trip kalibrerade.

### CHECK 3 — DA FIX-1: grep '^httpx==' requirements.txt exit 0
```
$ grep -qE '^httpx==' /srv/workspace/svarkor-matapp/bernie/1143.4-offer-ingest-referenspris-20260908/requirements.txt
HTTPX_GREP_EXIT=0
```
`requirements.txt` innehåller raden `httpx==0.28.1` (pinned runtime-dep). Offline-ingest-
alternativet förkastat: gaten (gate-p4) kräver att httpx-runtime-deps finns i deploy-miljön.

### CHECK 4 — regressionskydd (Phase 2-bas intakt; offers-tabellen bär referenspris)
```
$ ~/p4-venv/bin/python3 -c "import app.db; from app.models import offers_db; print('offers Base OK, has regular_price_cents:', 'regular_price_cents' in [c.name for c in offers_db.Offer.__table__.columns])"
offers Base OK, has regular_price_cents: True
DOD_IMPORT_EXIT=0
```

## 4. Filer i deliverable-trädet (source-only)
```
app/__init__.py
app/config.py                  # GrocerConfig + CHAIN_MAP (POC-shape återbrukad)
app/db.py                      # Phase 2 — boot/session (oförändrad bas)
app/ingest/__init__.py
app/ingest/grocer.py           # pull_grocer + referenspris-passthrough + parse_swedish_kr
app/ingest/normalizer.py       # RawOffer->NormalizedOffer m/ referenspris + is_extraprice-flagga
app/ingest/ingest.py           # ingest_week(pull->normalize->upsert), IngestResult
app/ingest/willys_mock.py      # inspelad willys-feed + injicerad httpx-lik MockSession (HAL-seam)
app/models/{__init__,users,profile,offers_db}.py  # Phase 2 (offers bär regular/savings)
database.py                    # shared Base + init_db (Phase 2)
harness_ingest.py              # gate-C3-harness (green + red two-sided calibration)
harness_self_test.py           # Phase 2 self-test (bibehållen)
requirements.txt               # + httpx==0.28.1 (DA FIX-1)
```

## 5. Noteringar för senare faser
- Phase 6 (optimizer) läser `regular_price_cents`/`savings_cents` från offers + räknar andelen
  `is_extraprice`-ingredienser ≥0.5 — referenspriset är nu persisterat och mätbart (closure-gap 1
  stängt; "majoritet" mätbar).
- `is_extraprice` är beräknad i normaliseringssteget (ej i DB, per map öppna fråga 2) — swapbar
  utan att röra motor-logik; Phase 6 kan härleda den själv från regular vs price om den föredrar.
- Willys referenspris hämtas från `comparePrice` (strängform → `parse_swedish_kr`), fallback
  `lowestHistoricalPrice.value`. ICA/coop token (map öppna fråga 1) verifieras INTE här —
  denna fas bevisar willys-öppen (den enda VERIFIED-källan); ica/coop förblir PLAUSIBLE-UNCHECKED.
- httpx-pinnen i `requirements.txt` är deploy-runtime (ej dev-only) — DA FIX-1 mönstret från
  Phase 2 (sqlalchemy) utökat till feed-fetch-runtime.

## 6. Verifieringsnivå
- Alla claims i §3 är VERIFIED — kommandon körda mot det publicerade trädet denna exekvering
  (pasted output ovan med verkliga exit-koder). Grönt = DoD-krav, rött = anti-false-green-trip.
- Ingen self-verifikation: C3 (dobbie) sätter slutgiltig `# VERDICT:`.

VERIFY_EXIT=0
