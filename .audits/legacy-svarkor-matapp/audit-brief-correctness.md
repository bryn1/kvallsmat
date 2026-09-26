# [type:test] audit: korrekthet — kör sviten, error paths (matapp)

Du är GATE. Adversarial korrekthets-audit av matapp POC-källan.

## Uppgift
1. Kör testsviten på POC-källan. OBS: POC-källan med root-route-fixen ligger i
   /srv/workspace/svarkor-matapp-root-route/dobbie/922.1-root-route-src-20260903/ (68 tester gröna
   enligt tidigare bevis — verifiera att de fortfarande är gröna). Hosting-kopian:
   /srv/workspace/hosting/apps/matapp/.
   OBS fälla: `dotnet test --no-restore`-mönstret gäller ej här, men stale __pycache__/obj kan
   ge falskt grönt — kör färskt.
2. Error paths: /api/menu utan params (422), ogiltig butik, ogiltigt veckonummer, DB saknas,
   feed nere. Hanteras de eller sväljs?
3. Edge cases: tom DB (ingen seed), samtidiga requests, saknad STATE_DIRECTORY.
4. Död kod / oåtkomliga grenar i app/routers + motor-src.
5. Jämför med framtidsversionens tester om sådana finns i 4d220cd (git show).

## DoD / Acceptance
DoD: Testsvit körd FÄRSKT med utdata i evidence-filen (antal tester, pass/fail, exit-kod); error-path-tabell route → input → beteende → bedömning; varje påstående märkt VERIFIED/UNVERIFIED; rapport sparad som /srv/workspace/svarkor-matapp/audit/correctness.md med VERIFY_EXIT=0.
