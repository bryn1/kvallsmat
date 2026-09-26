# [seat:dobbie] [type:test] matapp fixrunda 2-verifiering (tredje försöket) — mät själv, spara rapporten

Du är GATE. Verifiera fixrunda 2 (gren matapp-fixround, /srv/workspace/hosting) mot
audit-fynden F1, F2, F3 i /srv/workspace/svarkor-matapp/audit/security.md. Lita inte på
kodarens påståenden — mät själv.

VARNING: två tidigare försök (1233.2, 1233.3) markerades completed_unverified utan att
deras DoD uppfylldes — ingen rapportfil skapades. En tidigare körning lämnade bevis i
/tmp/mv-f1 (boot.log: 49x401 → 120x429, state-dir DB skapad) men ingen rapport. Denna
gång är RAPPORTFILEN huvudartefakten: skriv den löpande, inte i efterhand.

## Uppgift
1. git log matapp-fixround: F1 (env-var) egen commit; F2/F3 en till. Ocommitat arbete = FAIL.
2. F1: boota appen med STATE_DIRECTORY satt och repo read-only (chmod 444 eller read-only
   bind) — DB-fil ska skapas i state-dir, ingen OperationalError.
3. F2: 50 dåliga logins i snabb följd mot existerande användarnamn — lockout/429 ska trigga.
   Under lockout: korrekt lösenord ska INTE logga in.
4. F3: mät svarstid login existerande vs obefintligt användarnamn, 10x vardera — skillnad < 2x.
5. Kör hela testsviten färskt (städade __pycache__/.pytest_cache).
6. Regressionscheck: /health 200; /api/profile + /api/menu utan session = 401 (aldrig 200).

## DoD / Acceptance
DoD: /srv/workspace/svarkor-matapp/audit/fixround2-verify.md exists (checked with
`test -f`, exit 0) and contains: the literal string 'VERIFY_EXIT=0'; the string
'F1' with a VERIFIED or UNVERIFIED tag; the string 'F2' with a VERIFIED or
UNVERIFIED tag; the string 'F3' with a VERIFIED or UNVERIFIED tag; git-log output
containing the commit line '8e4aa9b'. The file MUST exist at close time — a close
without it is a failed delivery regardless of runner status.
