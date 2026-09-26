# PHASE 2 (T1) db-foundation — BUILD EVIDENCE (kort 1143.1)

**Seat:** bernie · **Datum (UTC):** 2026-09-08 · **Kort:** 1143.1 (Phase 2 T1 db-foundation)
**Deliverable (source-only tree):** `/srv/workspace/svarkor-matapp/bernie/1143.1-db-foundation-20260908/`
**Gränssnitt mot gate C1 (dobbie):** denna fil = byggarens evidens; C1 graderar till
`# VERDICT:` PASS/FAIL.

# VERDICT: PASS (builder-side; await C1 grader)

> Byggaren deklarerar sig klar och allt ovanstående DoD är kört med grönt resultat.
> C1 (dobbie) är den som sätter slutgiltig VERDICT-rad i sin egen gate-evidence.

---

## 1. Vad byggdes (closure av Phase 2-krav, PHASE0.md §P Phase 2)

| Krav (gate C1) | Leverans |
|---|---|
| `users`-tabell deklarerad på delade `database.Base` FÖRE `init_db` (fix-2-idiom) | `app/models/users.py` — `class User(Base)` på `database.Base`, importeras i `app/db.py` modul-scope före `init_db` |
| `profile`-tabell deklarerad på delade `database.Base` FÖRE `init_db` | `app/models/profile.py` — `class Profile(Base)` + FK till `users`, importeras före `init_db` |
| `offers.regular_price_cents`/`savings_cents`-kolumn finns (stänger closure-gap 1) | `app/models/offers_db.py` — `regular_price_cents`, `savings_cents` kolumner på `Offer` |
| Delad `database.Base` + `init_db` (motor/Kvällsmats-idiom) | `database.py` — `Base = declarative_base()`, `make_engine`, `get_session`, `init_db` (idempotent `create_all`) |
| Fix-2-idiom garanterat (modeller före init_db) | `app/db.py` — importerar `app.models` på modul-scope, `boot()` kör `init_db(engine)` |
| sqlalchemy runtime-dep (ej dev-only, DA FIX-1-mönster) | `requirements.txt` — `sqlalchemy==2.0.52` pin (deploy-runtime) |
| Harness self-test green + avsiktligt trasig modell röd | `harness_self_test.py` — se §3 |

## 2. DoD — exekverad på det publicerade trädet

Katalogen `/srv/workspace/svarkor-matapp/bernie/1143.1-db-foundation-20260908/`.

**DoD-import (exakt gate-kommando), med sqlalchemy 2.0.52 (verifierad PRESENT):**
```
$ cd /srv/workspace/svarkor-matapp/bernie/1143.1-db-foundation-20260908
$ ~/affar-cleanclone-venv/bin/python3 -c "import app.db; from app.models import users, profile, offers_db; print(users.Base, profile.Base)"
<class 'sqlalchemy.orm.decl_api.Base'> <class 'sqlalchemy.orm.decl_api.Base'>
DOD_IMPORT_EXIT=0
```

**grep regular_price_cents i offers-modellen:**
```
$ grep -c 'regular_price_cents' app/models/offers_db.py
1
Grep-count 1 >= 1  -> OK
```

## 3. Harness self-test (anti-false-green) — publicerat träd, exit 0

```
$ ~/affar-cleanclone-venv/bin/python3 harness_self_test.py
[GREEN] users.Base  == database.Base : <class 'sqlalchemy.orm.decl_api.Base'>
[GREEN] profile.Base== database.Base : <class 'sqlalchemy.orm.decl_api.Base'>
[GREEN] offers.Base == database.Base : <class 'sqlalchemy.orm.decl_api.Base'>
[GREEN] offers columns include regular_price_cents & savings_cents
[GREEN] init_db created users, profile, offers in /tmp/matapp-p2-v02dfrnx/harness.db
[GREEN] app.db.boot() ran init_db with all tables registered on Base
GREEN-CASE-EXIT=0
[RED] broken offer model lacks regular_price_cents -> correctly trips
HARNESS RESULT: PASS (green DoD + anti-false-green red trip)
[DoD-import] rc= 0
[DoD-import] stdout: <class 'sqlalchemy.orm.decl_api.Base'> <class 'sqlalchemy.orm.decl_api.Base'>
HARNESS_EXIT=0
```

Red-case bekräftar att harnessen ÄR falskt-grönt-träffsäker: en modell som saknar
`regular_price_cents` (dvs closure-gap 1 öppet) gick RÖTT → harnessen ljuger inte.

## 4. Filer i deliverable-trädet (source-only, inga build-artefakter)

```
app/__init__.py
app/db.py                 # boot + session; FIX-2 (modeller före init_db) på modul-scope
app/models/__init__.py    # exporterar users, profile, offers_db
app/models/users.py       # User  (users-tabell på shared Base)
app/models/profile.py     # Profile (profile-tabell: persons, meal_days, kron_budget, selected_stores)
app/models/offers_db.py   # Offer + regular_price_cents/savings_cents (closure-gap 1)
database.py               # shared Base + init_db (Kvällsmats-idiom)
harness_self_test.py      # green-DoD + anti-false-green red-trip
requirements.txt          # sqlalchemy==2.0.52 etc. (deploy-runtime, ej dev-only)
```

## 5. Noteringar för senare faser
- `profile`-tabellen bär redan fälten Phase 5 (T4) kräver: `persons`, `meal_days`,
  `kron_budget`, `selected_stores` (kap MAX 3, FK till `users`) — Phase 5 lägger bara
  auth-skyddad `/api/profile` ovanpå.
- `offers`-modellen är den nya-schema-hemvisten för offers med referenspris; Phase 4
  (ingest) skriver `regular_price_cents`/`savings_cents`, Phase 6 (optimizer) läser dem.
- sqlalchemy-pinnen ligger i deploy-`requirements.txt` (inte dev-only) — DA FIX-1-mönstret.

## 6. Ad-hoc verification pass (2026-09-08, hermes-verify)

Kört mot det publicerade trädet `/srv/workspace/svarkor-matapp/bernie/1143.1-db-foundation-20260908/`
via `/tmp/hermes-verify-db-foundation-1143.1.py` (temp, hermes-verify-prefix, bortstädat efteråt):

```
[1] DoD import rc=0: DoD-import OK <class 'sqlalchemy.orm.decl_api.Base'> <class 'sqlalchemy.orm.decl_api.Base'>
[2] grep(regular_price_cents) in offers_db.py = 1
[3] harness rc=0 → HARNESS RESULT: PASS (green DoD + anti-false-green red trip)
[4] init_db rc=0: init_db created: ['offers', 'profile', 'users']
VERIFY RESULT: PASS (ad-hoc)
VERIFY_EXIT=0
```

Detta är AD-HOC-verifiering (riktad mot ändrat beteende), INTE en kanonisk svit —
projektets gate-svit är C1/dobbie, som graderar denna byggares evidens.

VERIFY_EXIT=0
