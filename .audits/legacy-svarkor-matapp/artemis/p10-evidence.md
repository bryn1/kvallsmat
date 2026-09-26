# Phase 10 (T9) post-publish — GATE C9 evidence (kort 1164.8)

# VERDICT: FAIL

Full evidence + calibration selftest:
`/srv/workspace/svarkor-matapp/artemis/1164.8-gate-c9-postpublish-evidence-20260908.md`
Kört av artemis (grader) 2026-09-08 UTC. Gate-baren kördes exakt som DoD:n skriver.

Kort: `postpublish-accept.sh --url https://sibbamala.com/matapp/ --path api/auth/me
--path api/auth/login --path api/profile --path api/menu --require Konto ... --flow ...
--vision-expect Konto --vision-expect Profil` → **ACCEPT_EXIT=1 (RESULT=FAIL)**.

Varför rött (inte ett tooling-haveri, utan verklig brist):
1. Live-URL:n server **POC-versionen** (meny 18-rätter, fanor Butiker/Veckomeny), inte
   framtidsversionen. `product.html` sha256 == hosting-träds POC-index byte-identiskt.
2. `/matapp/api/auth/me|login` + `/matapp/api/profile` → **404** (auth+profile saknas live).
3. Varje framtids-flöde rött: `a[data-page="profile|suggestions|auth"]` finns ej i DOM:n.
4. Vision (lanef-27b, riktig pixel-check) ser ej "Konto"/"Profil" — de finns inte.

Bevarade gröna bevis (POC:en själv fungerar): 200 + not-blank pixels (stddev 0.279,
4885 colors), 11/11 assets 2xx, **0 konsolfel, 0 asset-404**, 0 sidfel efter interaktion.

Kalibrerad: samma gate går GRÖN på en fungerande lokal sajt med Konto/Profil-flöden
(`postpublish-calib2-20260908/RESULT.txt` RESULT=PASS, SELFTEST_RC=0; första calib-körningen
gick t.o.m. röd enbart på favicon-404 — gate:n är inte slapp). Gaten kan alltså gå grönt
— röd ovan = verklig brist, inte tooling-haveri. Vision-leden är separat bevisad live:
`--vision-expect Butiker` gick GRÖN på sibbamala (lanef-27b ser pixlarna korrekt).

CONSEQUENCE: project DONE-bar ej uppfylld; [onfail:1164.7] → T9 publiceringen (Phase 9/10)
är inte genomförd — framtidsversionen (Phase 7 api-lager + Phase 8 frontend) är aldrig
publicerad till hosting-repot. Evidens: `_scratch/postpublish-c9-11648-20260908/RESULT.txt`.

VERIFY_EXIT=1
