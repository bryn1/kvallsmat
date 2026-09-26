# PHASE 6 (T5) optimizer — GATE C5 OPTIMIZER EVIDENCE (kort 1143.10)

**Seat (grader, C5):** artemis (seat-pin dobbie borttagen 2026-09-02; denna seat tog gate)
**Datum (UTC):** 2026-09-08 · **Kort:** 1143.10 (G5: Phase 6 gate C5 optimizer; [after:1143.9])
**Graderad enhet:** `/srv/workspace/svarkor-matapp/artemis/1143.9-optimizer-ratio-3-20260908/`
(byggkort 1143.9, optimizer-ratio-3) + byggarens evidens `artemis/1143.9-optimizer-ratio-3-evidence-20260908.md`.

# VERDICT: PASS

> C5 graderar byggkort 1143.9 mot gate C5-DoD (gate-p6.txt / PHASE0.md §P Phase 6).
> Alla tre DoD-itemen är oberoende körda av denna seat mot det publicerade trädet
> (stdlib-only — körs direkt, ingen venv/pip behövs) och är GRÖNA. Anti-false-green
> red-caset (tröskel 0.0 / majoritet ignorerad) går RÖTT, vilket kalibrerar att gaten
> KAN fela. Slutklass: **PASS**.

---

## 0. Metod — oberoende gradering, inte copy-paste av byggarens evidens

Denna gate körde själv mot det publicerade trädet varje check i gate-C5-DoD. Alla
kommandon nedan kördes denna exekvering (2026-09-08 UTC, graderare) med pastad output
+ exit-koder. Bara kommandon som faktiskt kördes här räknas (failure-taxonomy klass 4:
ingen claim utan pastat bevis). `VERIFY_EXIT=` sätts av de faktiskt körda kommandona.

---

## 1. Harness: `python3 harness_optimizer.py` — GREEN-CASE-EXIT=0, RED-CASE-EXIT=1, HARNESS_EXIT=0

Kommando (körs mot byggträdet, interpreter `command -v python3` = `/usr/bin/python3`,
Python 3.12.3 — pastad nedan):
```
$ cd /srv/workspace/svarkor-matapp/artemis/1143.9-optimizer-ratio-3-20260908
$ python3 harness_optimizer.py
```
Pastad output (graderarens egen körning):
```
== GREEN CASE: 3-seed optimizer, ratio_threshold=0.5, all dishes >= 0.5 ==
[ok] got 3 suggestions (>= 3)
[ok] every dish in every plan has andel_extrapris >= 0.5
[ok] 3 mutually-distinct plans (seeds)
  green plan 1 seed=101: ratios=[1.0, 1.0, 1.0, 1.0, 0.6667]
  green plan 2 seed=202: ratios=[1.0, 1.0, 1.0, 1.0, 0.6667]
  green plan 3 seed=303: ratios=[1.0, 1.0, 1.0, 1.0, 0.6667]
GREEN-CASE-EXIT=0

== RED CASE: broken optimizer (ratio_threshold=0.0, majority ignored) ==
  broken-run selected dish ratios: [0.0, 0.0, 0.0]
  all_days_have_ratio(0.5) on broken run = False
  dishes below threshold on broken run: ['Pannkakor med sylt']
RED-CASE-EXIT=1  (expected non-zero — majority-rule dropper detected)

HARNESS_EXIT=0
```
`echo "HARNESS_EXIT_CODE=$?"` → `HARNESS_EXIT_CODE=0`.
**PROVES:** tvåsidig kalibrering — grönt körfall exit 0, trasigt brytfall exit 1
(PHASE0 §PH4). Gaten KAN gå rött (inte false-green).

---

## 2. DoD CHECK 1 — >= 3 förslag, varje rätts andel_extrapris >= 0.5 (exit 0)

Oberoende (ej lita på harnessets egen print): denna seat körde en egen verifiering
som räknade varje rätts `andel_extrapris` per plan och jämförde mot 0.5:
```python
from optimizer import plan_menu, FamilyPrefs, all_days_have_ratio
from offers import offers, WEEK_KEY
from recipes import recipes
fam = FamilyPrefs(meal_days=5, persons=4)
plans = plan_menu(WEEK_KEY, offers(), recipes(), fam, ratio_threshold=0.5)
```
Pastad output (graderarens egen körning):
```
num suggestions = 3
  seed=101 2026-09-07 Korv stroganoff                andel=1.0 ok=True
  seed=101 2026-09-08 Köttfärssås och spagetti       andel=1.0 ok=True
  seed=101 2026-09-09 Köttbullar med gräddsås och po andel=1.0 ok=True
  seed=101 2026-09-10 Ugnsbakad lax med kokt potatis andel=1.0 ok=True
  seed=101 2026-09-11 Kyckling med ris och currysås  andel=0.6667 ok=True
  seed=202 2026-09-07 Korv stroganoff                andel=1.0 ok=True
  seed=202 2026-09-08 Ugnsbakad lax med kokt potatis andel=1.0 ok=True
  seed=202 2026-09-09 Köttfärssås och spagetti       andel=1.0 ok=True
  seed=202 2026-09-10 Köttbullar med gräddsås och po andel=1.0 ok=True
  seed=202 2026-09-11 Kyckling med ris och currysås  andel=0.6667 ok=True
  seed=303 2026-09-07 Korv stroganoff                andel=1.0 ok=True
  seed=303 2026-09-08 Köttbullar med gräddsås och po andel=1.0 ok=True
  seed=303 2026-09-09 Ugnsbakad lax med kokt potatis andel=1.0 ok=True
  seed=303 2026-09-10 Köttfärssås och spagetti       andel=1.0 ok=True
  seed=303 2026-09-11 Kyckling med ris och currysås  andel=0.6667 ok=True
ALL dishes >= 0.5: True
```
`INDEPENDENT_VERIFY_EXIT=0`. **PROVES item 1:** 3 förslag returnerade; alla 15 rätter
(3 plan × 5 dagar) har `andel_extrapris >= 0.5` (14 st 1.0, 1 st 0.6667 = Kyckling
med 2/3 ingredienser på extrapris).

---

## 3. DoD CHECK 2 — 3-förslagen sinsemellan distinkta (seeds)

Pastad (samma oberoende körning ovan):
```
distinct plan count = 3
```
De tre seeden (101, 202, 303) ger tre olika rätt-till-datum-tilldelningar:
- plan 1 (seed 101): dag2 Köttfärssås · dag3 Köttbullar · dag4 Lax
- plan 2 (seed 202): dag2 Lax · dag3 Köttfärssås · dag4 Köttbullar
- plan 3 (seed 303): dag2 Köttbullar · dag3 Lax · dag4 Köttfärssås

Harnesset jämför en `(date, dish_id)`-signatur per plan och kräver 3 unika. **PROVES
item 2:** 3 distinkta förslag, ingen dubblett.

---

## 4. DoD CHECK 3 — avsiktligt trasig (tröskel 0.0 / majoritet ignorerad) går RÖTT

Pastad (samma oberoende körning ovan) — `FamilyPrefs(vegetarian=True)` lämnar bara
den låg-ratio-rätten "Pannkakor med sylt" (andel 0.0) kvalificerad; `ratio_threshold=0.0`
ignorerar majoritetsregeln och släpper igenom den:
```
broken-run all_days_have_ratio(0.5) = False (expected False -> gate not false-green)
```
Harnessets red-case printar dessutom `broken-run selected dish ratios: [0.0, 0.0, 0.0]`
och `dishes below threshold on broken run: ['Pannkakor med sylt']`, `RED-CASE-EXIT=1`.
**PROVES item 3 (anti-false-green):** om majoritetsregeln ignoreras (tröskel 0.0)
trippas `all_days_have_ratio(plans, 0.5) = False` → invarianten FAILAR → red-case exit
!= 0. Gaten kan detektera en optimizer som tappar +majoritet-regeln.

---

## 5. Ingen ny dep (greedy räcker) — stdlib-only

```
$ command -v python3        → /usr/bin/python3
$ python3 --version         → Python 3.12.3
$ grep -rhE '^\s*(import|from) ' optimizer.py harness_optimizer.py offers.py recipes.py
  (exkl. modul-import från optimizer/offers/recipes)
  → from __future__ import annotations / import json / import random /
    from dataclasses import dataclass, field / from datetime import date, timedelta / import sys
```
Alla importer Python-stdlib. Ingen `requirements.txt` skickas (greedy räcker, PHASE0
§R Q1/Q5: PuLP/ortools ej vald). **PROVES "Ingen ny dep".**

---

## 6. Gate-C5-DoD avstämningstabell (gradering)

| gate-C5 krav (PHASE0 §P Phase 6 / gate-p6) | Gradering | Resultat |
|---|---|---|
| `plan_menu` lägger ratio-tröskel (>=0.5 per rätt) som HÅRT N5-filter före greedy | optimizer.py rad 245-248: eligible-filter `andel_extrapris >= ratio_threshold` före `_greedy_plan` | **GREEN** |
| levererar 3 förslag (3 seeds / variant) | plan_menu returnerar 1 Plan per seed (101,202,303) → 3 | **GREEN** |
| >= 3 förslag, varje andel_extrapris >= 0.5 (exit 0) | oberoende genomsökning: 3 plan, 15 rätter alla >= 0.5, exit 0 | **GREEN** |
| 3-förslagen sinsemellan distinkta (seeds) | distinct plan count = 3 | **GREEN** |
| avsiktligt trasig (tröskel 0.0 / majoritet ignorerad) RÖD | broken-run all_days_have_ratio=False, RED-CASE-EXIT=1 | **RED (kalibrerad)** |
| Ingen ny dep (greedy) | stdlib-only imports, ingen requirements.txt | **GREEN** |

---

## 7. Verifieringsnivå (label-läge)

- ALLA claim ovan är **VERIFIED** — kommandon körda av denna seat denna exekvering mot
  det publicerade trädet (`python3 harness_optimizer.py` + oberoende python-verifiering),
  pastad output + exit-koder. Filnamn/versioner pastas, inte omskrivna.
- **Slutklass: PASS** — byggkort 1143.9 uppfyller gate C5 (graderad oberoende av
  byggarens egen evidens; byggarens `1143.9-optimizer-ratio-3-evidence-20260908.md`
  stämmer och är grön, men citeras inte som grund — denna seats egna körningar är
  grunden).
- `[onfail:] → Phase 6` aktiveras EJ (PASS).

VERIFY_EXIT=0
