# [type:test] matapp fixrunda: verifiera F1/BUG-1/BUG-2/F2/F3-fixarna

Du är GATE. Verifiera att fixrundan (gren matapp-fixround i /srv/workspace/hosting)
faktiskt åtgärdar audit-fynden från MC 1188 — lita inte på kodarens påståenden.

Rapporter med fynden: /srv/workspace/svarkor-matapp/audit/security.md (F1, F2, F3) och
/srv/workspace/svarkor-matapp/audit/correctness.md (BUG-1, BUG-2).

## Uppgift
1. Checkout av grenen matapp-fixround, bekräfta att den baserar på 4d220cd-innehåll
   (auth/profil/3-förslag finns) och att POC-funktionaliteten inte regresserat.
2. F1: boota appen med STATE_DIRECTORY satt och repo read-only-simulerat — DB ska skapas
   i state-dir, ingen OperationalError.
3. BUG-1/BUG-2: GET /api/menu med week=9999-W99, 0000-W01, 2026-W54, 2026-W00 — alla ska
   ge 422 (inte 500, inte tyst fel datum).
4. F2: 50 dåliga logins i snabb följd — lockout ska trigga (inte 50 st 401 för evigt).
5. F3: timing för befintligt vs obefintligt användarnamn — mät, skillnaden ska vara
   försumbar (<2x, inte 37ms vs 2ms).
6. Kör hela testsviten färskt (städade caches). Regressionsjakt: POC-routes
   (/api/stores, /health) ska fortfarande bete sig som i auditens E13-bild.

## DoD / Acceptance
DoD: /srv/workspace/svarkor-matapp/audit/fixround-verify.md finns och innehåller, för vart
och ett av fynden F1, F2, F3, BUG-1, BUG-2, en mätning på gren matapp-fixround med
VERIFIED/UNVERIFIED-märkning; raden 'VERIFY_EXIT=0' med färsk svit-körning (68+ tester,
städade caches) finns i filen; regressionssektion med /api/stores + /health + /api/menu
probes mot fix-grenen finns i filen.
