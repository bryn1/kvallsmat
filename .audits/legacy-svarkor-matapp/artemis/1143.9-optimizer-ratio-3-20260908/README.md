# Phase 6 (T5) optimizer-ratio-3 — deliverable (kort 1143.9)

matapp framtidsversion, Phase 6, gate C5 (PHASE0.md §P Phase 6). Build card (T5),
seat artemis. Delivers the ratio-threshold menu optimizer + a two-sided harness.

## Files
- `optimizer.py`        — `plan_menu`: HARD ratio N5 filter (andel_extrapris >=
                          ratio_threshold, default 0.5) applied BEFORE greedy, and
                          n-variants (default 3) weekly Plans from 3 seeds.
                          `andel_extrapris(recipe, offers)` = fraction of the dish's
                          ingredients matched by an EXTRAPRIS offer.
                          `all_days_have_ratio(plans, threshold)` = invariant helper.
- `offers.py`            — recorded in-week offers (willys 2026-W37) carrying the
                          Phase-4 reference-price columns + `is_extraprice` flag.
- `recipes.py`          — recorded recipe set (C-RDB shape), incl. ONE deliberately
                          low-ratio dish ("Pannkakor med sylt", ratio 0.0) used to arm
                          the RED case.
- `harness_optimizer.py`— two-sided gate-C5 harness (green + red), stdlib only.

## Run
```
python3 harness_optimizer.py        # stdlib only, no venv/pip needed
```
Expected: GREEN-CASE-EXIT=0 (>=3 distinct suggestions, all dishes andel_extrapris >=
0.5) AND RED-CASE-EXIT=1 (broken threshold 0.0 lets a ratio-0.0 dish through ->
invariant fails). Overall HARNESS_EXIT=0 only when green==0 and red==1.

## Gate-C5 DoD mapping
- >= 3 suggestions, each dish andel_extrapris >= 0.5 (exit 0): green case.
- 3 suggestions mutually distinct (seeds): green case (dishes differ per seed).
- Deliberately broken (threshold 0.0 / majority ignored) goes RED: red case.

## No new dependency
Optimizer + harness use ONLY Python stdlib (json, random, dataclasses, datetime, sys).
No `requirements.txt` needed; greedy remains sufficient (PHASE0.md §R Q1/Q5, no PuLP).
