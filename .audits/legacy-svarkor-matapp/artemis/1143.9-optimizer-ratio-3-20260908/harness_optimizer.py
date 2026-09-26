"""Phase 6 (T5) optimizer-ratio-3 — two-sided HARNESS (gate C5 DoD).

Green + Red, self-contained, stdlib only (no new dep — greedy suffices). Mirrors the
two-sided calibration discipline (PHASE0.md §PH4): a gate that cannot go red is a
false-green gate, so the RED case is deliberate.

GREEN CASE (exit 0):
  plan_menu(week_key, offers, recipes, family, ratio_threshold=0.5) with 3 seeds
  must return >= 3 suggestions, where EVERY selected dish in EVERY plan has
  andel_extrapris >= 0.5, and the 3 plans are MUTUALLY DISTINCT (different
  dish-to-date assignments from the 3 seeds).

RED CASE (exit != 0):
  The deliberately-broken variant IGNORES the majority rule (ratio_threshold=0.0)
  and, under a family that leaves only the low-ratio dish eligible (vegetarian=True ->
  only Pannkakor, ratio 0.0), selects dishes with andel_extrapris < 0.5. The harness
  asserts the >= 0.5 invariant FAILS on that broken run (all_days_have_ratio False) —
  proving the gate is not false-green and can detect a dropper of the majority rule.
"""
from __future__ import annotations

import sys

from optimizer import (
    FamilyPrefs,
    andel_extrapris,
    all_days_have_ratio,
    plan_menu,
)
from offers import WEEK_KEY, offers
from recipes import recipes

THRESHOLD = 0.5
EXPECTED_VARIANTS = 3


def _day_map(plan):
    """{(date, seed): dish_title} signature used for distinctness comparison."""
    return tuple((d["date"], d["dish_id"]) for d in plan["days"])


def _run_green() -> int:
    print("== GREEN CASE: 3-seed optimizer, ratio_threshold=0.5, all dishes >= 0.5 ==")
    fam = FamilyPrefs(meal_days=5, persons=4)
    plans = plan_menu(WEEK_KEY, offers(), recipes(), fam, ratio_threshold=THRESHOLD)

    # 1) >= 3 suggestions
    if len(plans) < EXPECTED_VARIANTS:
        print(f"[RED-safety] expected >= {EXPECTED_VARIANTS} plans, got {len(plans)}")
        return 1
    print(f"[ok] got {len(plans)} suggestions (>= {EXPECTED_VARIANTS})")

    # 2) every dish in every plan satisfies andel_extrapris >= 0.5
    if not all_days_have_ratio(plans, THRESHOLD):
        print("[RED-safety] a selected dish fell below the 0.5 ratio threshold")
        return 1
    lows = [
        (d["dish_id"], d["andel_extrapris"])
        for p in plans for d in p["days"]
        if d["andel_extrapris"] < THRESHOLD - 1e-9
    ]
    if lows:
        print(f"[RED-safety] below-threshold dishes: {lows}")
        return 1
    print(f"[ok] every dish in every plan has andel_extrapris >= 0.5")

    # 3) the 3 suggestions are mutually distinct (different dish-to-date from seeds)
    sigs = {_day_map(p) for p in plans}
    if len(sigs) < len(plans):
        print(f"[RED-safety] only {len(sigs)} distinct plans, expected {len(plans)}")
        return 1
    print(f"[ok] {len(sigs)} mutually-distinct plans (seeds)")

    for i, p in enumerate(plans, 1):
        dishes = " | ".join(d["dish_id"] for d in p["days"])
        ratios = [d["andel_extrapris"] for d in p["days"]]
        print(f"  green plan {i} seed={p['seed']}: ratios={ratios}")
        print(f"      dishes: {dishes}")
    print("GREEN-CASE-EXIT=0")
    return 0


def _run_red() -> int:
    print("\n== RED CASE: broken optimizer (ratio_threshold=0.0, majority ignored) ==")
    # The low-ratio dish is genuinely below threshold.
    pannkakor = next(r for r in recipes() if r.title.startswith("Pannkakor"))
    low_ratio = andel_extrapris(pannkakor, offers())
    assert low_ratio < THRESHOLD, f"expected low-ratio dish, got andel={low_ratio}"

    # Broken config: threshold 0.0 IGNORES the majority rule; family leaves only the
    # low-ratio vegetarian dish eligible, so it gets selected and must FAIL the invariant.
    fam = FamilyPrefs(meal_days=5, persons=4, vegetarian=True)
    plans = plan_menu(WEEK_KEY, offers(), recipes(), fam, ratio_threshold=0.0)
    selected_ratios = [d["andel_extrapris"] for p in plans for d in p["days"]]
    ok_invariant = all_days_have_ratio(plans, THRESHOLD)

    print(f"  broken-run selected dish ratios: {selected_ratios}")
    print(f"  all_days_have_ratio(0.5) on broken run = {ok_invariant}")
    if ok_invariant:
        print("[false-green] broken optimizer still satisfied the >= 0.5 invariant!")
        return 1
    # Also confirm the low-ratio dish is what slipped through.
    slipped = [d["dish_id"] for p in plans for d in p["days"]
               if d["andel_extrapris"] < THRESHOLD - 1e-9]
    print(f"  dishes below threshold on broken run: {sorted(set(slipped))}")
    print("RED-CASE-EXIT=1  (expected non-zero — majority-rule dropper detected)")
    return 1


def main() -> int:
    green_exit = _run_green()
    red_exit = _run_red()
    total = 0 if (green_exit == 0 and red_exit == 1) else 1
    print(f"\nHARNESS_EXIT={total}")
    return total


if __name__ == "__main__":
    sys.exit(main())
