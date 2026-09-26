# PHASE 3 (T2) auth — BUILD EVIDENCE (short 1143.3)

**Seat:** dobbie (assigned; seat pinning removed 2026-09-02) · **Datum (UTC):** 2026-09-08
**Kort:** 1143.3 (Phase 3 T2 auth) · **Förälder:** 1143 · **Gränssnitt mot gate C2 (G2, kort 1143.4):**
denna fil = byggarens evidens; C2 graderar till `# VERDICT:` PASS/FAIL.

**Deliverable (source-only tree):** `/srv/workspace/svarkor-matapp/dobbie/1143.3-auth-20260908/`

# VERDICT: PASS (builder-side; await C2 grader)

> Byggaren deklarerar sig klar och allt DoD nedan är kört med grönt resultat på det
> PUBLICERADE trädet. C2 (1143.4, dobbie) är den som sätter slutgiltig VERDICT-rad i sin
> egen gate-evidence.

---

## 1. Vad byggdes (closure av Phase 3-krav, PHASE0.md §P Phase 3 — gate C2)

| Krav (gate C2) | Leverans |
|---|---|
| argon2-cffi-hashning, **Argon2id 19 MiB / t=2 / p=1** | `app/security.py` — `PasswordHasher(time_cost=2, memory_cost=19*1024, parallelism=1)`; `hash_password`/`verify_password` delegerar till riktiga argon2 (ingen egen encoder) |
| Stänger **closure-gap 2** (argon2-cffi var MISSING) | `requirements.txt` — `argon2-cffi==25.1.0` + `argon2-cffi-bindings==21.2.0` pin (deploy-runtime, ej dev-only) |
| Opak session-cookie (HttpOnly+Secure+SameSite) | `app/security.py` cookie-policy + `app/routers/auth.py` `response.set_cookie(..., httponly=True, secure=True, samesite="lax")`; token är `secrets.token_urlsafe(32)` (opak, ingen användardata) |
| `/api/auth/login\|logout\|me` | `app/routers/auth.py` — login (401 på fel creds), logout (invaliderar session), me (401 utan giltig session) |
| Server-sidig session (auth-seam, ingen egen krypto) | `app/auth_service.py` — SessionStore (token→username) + authenticate/login/current_user/logout |
| Bygger på Phase 2 db-foundation | `users.password_hash` kolumn (fanns redan), `app/db.py` boot + shared Base återanvänds |

## 2. DoD — exekverad på det PUBLICERADE trädet

Katalog: `/srv/workspace/svarkor-matapp/dobbie/1143.3-auth-20260908/`

**DoD (a): `grep -i argon2 requirements.txt` ≥ 1 pin**
```
$ cd /srv/workspace/svarkor-matapp/dobbie/1143.3-auth-20260908
$ grep -i argon2 requirements.txt
# Phase 3 (T2) auth — closure-gap 2: argon2-cffi was MISSING, now pinned.
# Argon2id hashing (app/security.py) is a RUNTIME dep of /api/auth/* — must ship
# in the deploy env, not dev-only. argon2-cffi-bindings is the native wheel it needs.
argon2-cffi==25.1.0
argon2-cffi-bindings==21.2.0
GREP_EXIT=0   (>= 1 pin: argon2-cffi==25.1.0, argon2-cffi-bindings==21.2.0)
```

**DoD (b): auth-harness verifierar lösenords-hash + session-roundtrip, exit 0, fel lösenord RÖD**
```
$ /home/dobbie/matapp-p3-venv/bin/python3 -W ignore::DeprecationWarning harness_self_test.py
[GREEN] argon2 pins in requirements.txt: 5 -> [... argon2-cffi==25.1.0, argon2-cffi-bindings==21.2.0]
[GREEN] argon2id hash + real-argon2 verify OK: $argon2id$v=19$m=19456,t=2,p=1$fBb8VRacP...
[GREEN] /api/auth/login->me->logout session roundtrip OK
[RED] wrong passwords fail verification (anti-false-green)
[RED] login with wrong password -> 401
HARNESS RESULT: PASS (green argon2id+session DoD + anti-false-green red trip)
HARNESS_EXIT=0
```

`m=19456` i hash-utdraget bekräftar exakt 19 MiB (19×1024=19456) — gate C2:s parametrar.
Harness testar ARGON2-verifiering genom riktiga `argon2.PasswordHasher.verify` (inte egen
encoder) och main() returnerar ackumulerad exit-kod (aldrig o-inkrementerad lokal).

## 3. Mutationsprov (anti-false-green — harness ljuger inte)

För att bevisa att harnessen KAN gå rött på en trasig build (inte bara sin egen encoder),
muteras `app/security.py` till `verify_password() -> True` (accepterar allt). Körningen gick
RÖTT, exit 3, och modulen återställdes (MD5-match):
```
[RED-FAIL] verify_password('hunter2-wrong') wrongly returned True
[RED-FAIL] verify_password('completely-different') wrongly returned True
[RED-FAIL] login with wrong pw returned 200, expected 401
HARNESS-FAIL: 3 anti-false-green check(s) not tripped
MUTATED_HARNESS_EXIT=3
md5sum app/security.py /tmp/security.py.bak  -> identiska (återställt)
```
Detta är mutation-proving (sensorgate-läxan): grönt på rent bygge + rött på trasig.
Demonstrerar avsiktligt fel lösenord → RÖD (DoD:s röda fall) samt att harness fångar en
verify som helt tar bort argon2-kontrollen.

## 4. Filer i deliverable-trädet (source-only, inga build-artefakter)

```
app/__init__.py
app/db.py                   # REUSE Phase 2: boot + session, FIX-2 (modeller före init_db)
app/database.py             # REUSE Phase 2: shared Base + init_db
app/models/{__init__,users,profile,offers_db}.py   # REUSE Phase 2
app/security.py             # NY: Argon2id 19MiB/t2/p1 hash/verify + session-cookie-policy
app/auth_service.py         # NY: server-sidig SessionStore + login/logout/current_user
app/routers/__init__.py
app/routers/auth.py         # NY: /api/auth/login|logout|me (FastAPI)
app/main.py                 # NY: app-assembly, inkluderar auth-router + boot på startup
harness_self_test.py        # NY: DoD-harness green + anti-false-green red
requirements.txt            # + argon2-cffi==25.1.0 / argon2-cffi-bindings==21.2.0 (runtime pin)
```

## 5. Noteringar för senare faser
- **Phase 5 (profile) auth-skyddad:** `app/auth_service.current_user(token)` + cookie-
  attributen är återanvändbara som FastAPI-dependency för att skydda `/api/profile/*`
  (oautentiserad → 401, som C4 kräver). `app/routers/auth.py` visar mönstret (läser cookie,
  current_user → None → 401).
- **DA FIX-1-skugga (OBS i brief):** `argon2-cffi` + `argon2-cffi-bindings` ligger i
  deploy-`requirements.txt` (runtime), INTE dev-only — samma mönster som sqlalchemy i PH2.
  Så argon2 är en deploy-runtime-dep, inte test-only.
- **Sessioner i minnet (Phase 3-scope):** SessionStore är in-memory (en process-restart
  tömmer dem). Acceptabelt för C2; Phase 7 (api-lager) kan backa store:n mot en DB-tabell
  om persistens krävs.
- **Körvenv för verifiering:** ren venv `/home/dobbie/matapp-p3-venv` (python3.12) med
  de pinnade runtime-deps + `httpx` (endast test). Detta undviker `.pth`-pollution från den
  gemensamma `venv-4845` (som pekar på en annan projects `.venv-4844`).

VERIFY_EXIT=0
