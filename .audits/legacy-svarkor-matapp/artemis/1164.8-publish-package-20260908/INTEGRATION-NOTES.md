# 1164.8 publish package — framtidsversion → hosting repo (INTEGRATION-NOTES)

Inte ett deploy-artefakt i sig: detta är färdigmonterat TRÄD + instruktioner för den som
har push-nyckeln (svarkor/henrik). Innehållet är den sammanslagna appen ur
`artemis/1164.7-stage-20260908/app-new` (T9-stage), kildekodekilde: bernie 1164.1 api-lager
+ Phase 8 frontend (1164.3) + POC-motorn `src/` (oförändrad).

## Vad som byts ut
- `apps/matapp/` — HELT utbyte av POC-versionen mot framtidsversionen:
  `app/` (auth+profile+api-lager+optimizer), `static/`+`templates/` (Konto/Profil/3-förslag-
  vyer, prefix-medveten api.js), `server.py` ($PORT-bind + STATE_DIRECTORY-rebase +
  montering av static/health/favicon), `requirements.txt` (lagga till argon2-cffi==25.1.0 +
  argon2-cffi-bindings==21.2.0 ovanpå POC-pins), `run_motor.py`+`src/` (oförändrad motor).
- `hosting.yaml` — appens egen manifest (repo-root-varianten; monorepo-formen är
  apps.yaml-posten som REDAN är korrekt: service, root apps/matapp, exec server.py, port 8141).
- `apps.yaml` — OFÖRÄNDRAD (posten matchar); medföljer bara som revisonskopia.

## Steg för den med push-nyckeln
1. I hosting-repets rotation: `rsync -a --exclude .data --exclude __pycache__ \
   <detta package>/apps/matapp/ apps/matapp/` (ta backup av POC:en i git-branch först).
2. `git add apps/matapp && git commit -m "matapp: publish framtidsversion (MC 1164.8 pkg)" \
   && git push` — vm106-pulltimern (≤5 min) rollerar enheten.
3. RÖLLBACK: `git revert` + push (enhets-återställning automatiskt).
OBS: kör INTE som rotens hosting.yaml — monorepo-reconcilern läser apps.yaml.

## Kända risker (läs före push)
- R1 ARGON2: vm106-körningen bygger requirements i app-venv; argon2-cffi-bindings behöver
  native wheel. Beprövat mönster finns i andra appar — verifiera att venv-buildern klarar det,
  annars faller auth till 500 vid första inloggning.
- R2 DATABAS: framtidsversionen skapar `users`/`profile`-tabeller i samma sqlite-fil som POC:en
  (StateDirectory). Nya tabeller är ofarliga; gamla `offers`-data bevaras.
- R3 FAVICON: server.py serverar /favicon.ico ur static/ — behåll static/favicon.ico i trädet.

## Verifierad före förpackning (artemis, 2026-09-08, vm105)
- Staged serve 127.0.0.1:8498: /health framtidsversion, authed-harness 10/11 gröna
  (RED-litmus höll; enda röda = 3 förväntade 401/404 console.error vid logged-out fetch —
  se bevisfil 1164.8-gate-c9-retest-*).
