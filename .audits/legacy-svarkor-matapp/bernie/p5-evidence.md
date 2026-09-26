# PHASE 5 (T4) profile — BUILD EVIDENCE (kort 1143.7)

**Seat:** bernie · **Datum (UTC):** 2026-09-08 · **Kort:** 1143.7 (Phase 5 T4 profile; parent 1143)
**Deliverable (source-only tree):** `/srv/workspace/svarkor-matapp/bernie/1143.7-profile-20260908/`
**Gränssnitt mot gate C4 (dobbie):** denna fil = byggarens evidens; C4 graderar till
`# VERDICT:` PASS/FAIL enligt `/srv/workspace/svarkor-matapp/briefs/gate-p5.txt`
(profil-roundtrip mot auth-session exit 0; oautentiserad /api/profile 401; trasig kron-budget RÖD).

# VERDICT: PASS (builder-side; await C4 grader)

> Byggaren deklarerar sig klar och hela Phase 5-DoD är kört med grönt resultat på det
> publicerade trädet (se §3 exekverad output). C4 (dobbie) sätter slutgiltig VERDICT-rad
> i sin egen gate-evidence.

---

## 1. Vad byggdes (closure av Phase 5-krav, PHASE0.md §P Phase 5 / gate C4)

| Krav (gate C4) | Leverans |
|---|---|
| Profil lagras mot autentiserad session | `app/profile_service.py` — `save_profile(user, data)` upsertar EN profilrad per `user_id` (kolumnen är UNIQUE) och `load_profile(user)` läser tillbaka samma värden, så PUT→GET-roundtrip återkommer IDENTISKT |
| Per-användare persisterat: persons, meal_days, kron-budget, 3 valda butiker | `app/profile_service.ProfileData` + `app/models/profile.py` (Phase 2: `persons`, `meal_days`, `kron_budget`, `selected_stores` ≤ `MAX_SELECTED_STORES=3`) |
| `/api/profile/*` auth-skyddad | `app/routers/profile.py` — `GET/PUT /api/profile`, varje handler beror på `_current_user_or_401` som löser den opaka `matapp_session`-cookien via Phase 3 `auth_service.current_user`; saknad/ogiltig session → **401, aldrig 200** |
| DoD: profil roundtrip mot auth-session exit 0 | `harness_self_test.py` GREEN-ROUNDTRIP (TestClient över https så Secure-cookien återkommer; login→PUT→GET identiskt). Se §3 CHECK 1 |
| DoD: oautentiserad GET /api/profile ger 401 (inte 200) | `harness_self_test.py` GREEN-401: GET och PUT utan session-cookie → 401. Se §3 CHECK 2 |
| DoD: avsiktligt trasig (kron-budget saknas) RÖD | `harness_self_test.py` RED-case: (a) riktiga `save_profile` RAISAR på saknad kron_budget; (b) muterad service som tyst droppar kron_budget fångas av roundtrip-jämförelsen (röde). Se §3 CHECK 3 + extern mutationsprofil §4 |
| Återbruk (reuse-first, STEP 0) | Återanvänder VERIFIED Phase 2 db-foundation (`database.py`, `app/models/{users,profile,offers_db}`, `app/db.py`) och Phase 3 auth (`app/security.py`, `app/auth_service.py`, `app/routers/auth.py`) genom att bygga ett komplett körbart träd på dem — inget nytt ark mot proven base |

## 2. Lingval & designnot (kod-disciplin)

Repo är helt Python (FastAPI/SQLAlchemy) — Python är rätt verktyg här, ingen port till Rust
(glue/persistence på befintlig stack; coding-discipline §Language-preference undantag).
Varje ny modul är en concern och under ~150 rader: `profile_service.py` (CRUD), `routers/profile.py`
(HTTP + auth-dependency), `harness_self_test.py`. Profilen läses bara via den autentiserade
`User` som sessionen pekar på (inget user-supplied user_id) — per-user-isolering är lagrad i
frågan, inte i klienten. `kron_budget` är REQUIRED i `ProfileBody` (pydantic 422 vid saknad)
och `save_profile` RAISAR `ValueError` om `kron_budget is None` — dubbel guard för gate-kravet.

## 3. DoD — exekverad på det publicerade trädet (fresh runtime venv `~/matapp-p5-venv`)

Runtime: `~/matapp-p5-venv/bin/python` med pins från trädets `requirements.txt`
(`fastapi==0.141.1, sqlalchemy==2.0.52, pydantic==2.13.4, argon2-cffi==25.1.0`) +
`httpx==0.28.1` (test-dep för TestClient, ej runtime — consistent med Phase 3 C2-gate-användning).

### CHECK 1 — profil roundtrip mot auth-session (exit 0) + MAX=3 + per-user
```
$ ~/matapp-p5-venv/bin/python harness_self_test.py   (GREEN-ROUNDTRIP-sektionen)
[GREEN] authenticated login OK (session cookie issued: 43 chars)
[GREEN] PUT /api/profile (auth) -> 200
[GREEN] GET /api/profile (auth) -> 200, read-back IDENTICAL to stored
[GREEN] roundtrip stored={'persons': 4, 'meal_days': 6, 'kron_budget': 1200, 'selected_stores': ['willys', 'ica', 'coop']}
[GREEN] roundtrip read  ={'persons': 4, 'meal_days': 6, 'kron_budget': 1200, 'selected_stores': ['willys', 'ica', 'coop']}
[GREEN] 4 selected_stores -> 422 (MAX=3 store_selection rule holding)
[GREEN] per-user isolation OK: bella has no profile (404)
GREEN-ROUNDTRIP-EXIT=0
```
Roundtripen läser tillbaka EXAKT det lagrade (`stored == read`), 4 butiker → 422 (MAX=3),
och en andra användare ser sitt eget tomma profil (404), inte alex' profil — per-user-persistens.

### CHECK 2 — oautentiserad GET /api/profile ger 401 (inte 200)
```
$ ~/matapp-p5-venv/bin/python harness_self_test.py   (GREEN-401-sektionen)
[GREEN] unauthenticated GET /api/profile -> 401 (NOT 200); auth-skyddad holding
[GREEN] unauthenticated PUT /api/profile -> 401 (auth-skyddad holding)
GREEN-401-EXIT=0
```
Utan session-cookie ger BÅDE GET och PUT 401 — aldrig 200.

### CHECK 3 — avsiktligt trasig (kron-budget saknas) RÖD (two-sided calibration)
```
$ ~/matapp-p5-venv/bin/python harness_self_test.py   (RED-sektionen)
[RED] missing kron_budget correctly rejected by save_profile: kron_budget is required and must be >= 0 (gate C4)
[RED] broken save (kron_budget dropped) read back: kron_budget=None
[RED] roundtrip integrity check DETECTED the dropped kron_budget
HARNESS RESULT: PASS (green roundtrip + green 401 + anti-false-green red trip)
HARNESS_EXIT=0
```
(a) Riktiga `save_profile` RAISAR på saknad kron_budget. (b) En muterad save som tyst skriver
kron_budget=None fångas av roundtrip-jämförelsen (läsback kron_budget=None → mismatch). Exit 0
ENDAST för att både grönt och rött triggade — annars exit 2/3/4.

## 4. OBEROENDE mutationsproov (grader-stil, extra anti-false-green)

Jag muterade `app/profile_service.py::load_profile` att droppa kron_budget (källnivå) i en
kopia och körde GREEN-roundtrip:
```
[MUTATION RED-trip: GREEN roundtrip FAILED on mutated build:
   roundtrip mismatch on kron_budget: stored 1200 read back None]
```
En build vars load tappar kron-budget går alltså RÖD på roundtrip-checken — PASS är inte
false-green. (Mutationen kördes på en kopia i `~/matapp-p5-mutation`, borttagen efter; det
publicerade trädet är ORÖRT — `grep -rn MUTATION` tom.)

## 5. Källgranskning — auth-skydd och kron-budget i källan

```
$ grep -n "Depends" app/routers/profile.py
37:def _current_user_or_401(request: Request) -> User:
48:                user: User = Depends(_current_user_or_401)) -> dict:
57:                user: User = Depends(_current_user_or_401)) -> dict:
$ grep -n "@router.get\|@router.put" app/routers/profile.py
46:@router.get("")
55:@router.put("")
$ grep -n "kron_budget" app/models/profile.py
34:    kron_budget = Column(Integer)            # kronor/week — MUST be present (Phase 5 gate)
$ grep -n "include_router" app/main.py
29:app.include_router(auth.router)
30:app.include_router(profile.router)
```
`kron_budget`-kolumnen är deklarerad på profile-modellen (Phase 2 Base), `_current_user_or_401`
kopplas till GET och PUT via `Depends` (auth-skydd), och profile-routern är inkopplad i appen.

## 6. Slutsats

Alla tre gate-C4-DoD-checkar är grönt körda på det publicerade trädet med pasted output:
(1) profil roundtrip mot auth-session exit 0 och IDENTISK lässback, (2) oautentiserad
GET/PUT /api/profile → 401 (inte 200), (3) avsiktligt trasig kron-budget går RÖD — bevisat
internt (RED-service-raises + muterad-save-fångad) OCH oberoende på källnivå (load droppar
budget → roundtrip RÖD). Återbruk av Phase 2 db-foundation + Phase 3 auth. Inga blockers.
Runtime-deps oförändrade från Phase 3 (ingen ny dep); httpx är test-only för harnessen.

VERIFY_EXIT=0
