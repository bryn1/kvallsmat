# [onfail:1227.1][cycles:2] [seat:dobbie] [type:test] matapp fixrunda 2: verifiera F2/F3 + F1-commit

Du är GATE. Verifiera fixrunda 2 (gren matapp-fixround, /srv/workspace/hosting) mot
audit-fynden F1, F2, F3 i /srv/workspace/svarkor-matapp/audit/security.md. Lita inte på
kodarens påståenden — mät själv.

## Uppgift
1. git log matapp-fixround: F1 (env-var) ska vara en EGEN commit; F2/F3 en (eller två) till.
   Ocommitat arbete = FAIL.
2. F1: boota appen med STATE_DIRECTORY satt — DB-fil ska skapas i state-dir, ingen
   OperationalError. (Replikera auditens E1-mätning.)
3. F2: 50 dåliga logins i snabb följd mot ett existerande användarnamn — lockout/429 ska
   trigga (inte 50 st 401 för evigt). Efter lockout: korrekt lösenord ska INTE logga in
   förrän lockout-tiden löpt ut.
4. F3: mät svarstid login med existerande vs obefintligt användarnamn, 10x vardera —
   skillnad < 2x (auditens baslinje var 37ms vs 2ms).
5. Kör hela testsviten färskt (städade caches). Regressionscheck: POC-routes /api/stores,
   /health ska fortfarande svara som i auditens E13-bild; /api/profile + /api/menu utan
   session = 401 (aldrig 200).

## DoD / Acceptance
DoD: /srv/workspace/svarkor-matapp/audit/fixround2-verify.md finns och innehåller, för vart
och ett av F1, F2, F3, en mätning på gren matapp-fixround med VERIFIED/UNVERIFIED-märkning;
raden VERIFY_EXIT=0 med färsk svit-körning (städade caches) finns i filen; regressionssektion
med /api/stores + /health + /api/profile + /api/menu probes finns i filen; git-log-utdata som
visar F1-committen finns i filen.
