# [seat:teddy] [type:code] matapp fixrunda 2: F2 rate-limit + F3 timing-jämnare + commit av F1

Föregående fixrunda (MC 1227.1) levererade bara F1 (env-var-fixen i server.py + DEPLOY.md,
ligger OCOMMITAT på gren matapp-fixround i /srv/workspace/hosting). Denna runda kompletterar
de återstående fynden från audit MC 1188.

Rapporter: /srv/workspace/svarkor-matapp/audit/security.md (F2, F3), correctness.md (BUG-1/2
= POC-scopade, INTE denna rundan — framtidsversionens /api/menu har ingen week-param).

## Uppgift (gren matapp-fixround, /srv/workspace/hosting)
1. **Commit F1 först** — de ocommitade ändringarna i server.py + DEPLOY.md är verifierade
   och ska in som en egen commit ("matapp: F1 fix — MATAPP_DB_URL env-var (audit 1188.9 F1)")
   innan nytt arbete börjar. Master ska alltid vara sant: commit per sammanhängande steg.
2. **F2 rate-limit/lockout på POST /api/auth/login** (app/routers/auth.py + app/auth_service.py):
   in-memory räknare per username (samma scope som SessionStore), t.ex. 5 fel inom 15 min
   → 429/lockout i 15 min. Lyckad login nollställer räknaren. Trådsäkert (lock), som
   SessionStore.
3. **F3 timing-jämnare** (app/auth_service.py authenticate()): vid obefintligt användarnamn,
   kör argon2-verify mot en modul-nivå dummy-hash (genererad vid import från en fast dummy-
   sträng) så att svarstiden matchar existerande användarnamn. Mål: skillnad < 2x.
4. **Nya tester** för F2 (lockout triggar efter N fel, nollställs vid lyckad login) och F3
   (timing-mätning befintlig vs obefintlig användare) i POC-trädets tests/-struktur —
   skapa tests/ för framtidsversionen om den saknar det (den gör det).
5. Kör hela sviten färskt (städade __pycache__/.pytest_cache). Allt grönt.

## DoD / Acceptance
DoD: /srv/workspace/svarkor-matapp/audit/fixround2-evidence.md finns och innehåller: (a)
git log på matapp-fixround som visar F1-committen + F2/F3-committen; (b) färsk pytest-utdata
med antal tester och VERIFY_EXIT=0; (c) testutdata som visar lockout-trigging (429/lockout
efter N fel) och timing-mätning (<2x skillnad). Varje påstående märkt VERIFIED/UNVERIFIED.
