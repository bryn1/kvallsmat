"""RED tests for M5 planner (C6) — deterministic constraint solver.

Run: python -m pytest tests/test_planner.py
The planner is deterministic (N7): fixed ``seed``, no wall-clock randomness,
idempotent for identical inputs. Family constraints (budget / måltidsantal /
personer / allergier / vegetariskt) are applied locally (N5). The planner
maximizes offer-hits and degrades cleanly to recipe-only for days with no
matching offer (logged).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from recipes.store import Recipe
from offers_db.store import Offer
from planner.menu import plan_menu, FamilyPrefs, Plan


# ---------------------------------------------------------------- fabricators


def make_recipe(title, *, servings=4, vegetarian=0, budget_tier="mid",
                allergens=(), category="husmanskost"):
    return Recipe(
        title=title, category=category, servings=servings,
        ingredients_json=json.dumps([{"name": "x", "qty": 1, "unit": "st"}]),
        allergens_json=json.dumps(list(allergens)),
        vegetarian=vegetarian, budget_tier=budget_tier,
        recipe_id=abs(hash(title)) % 100000,
    )


def make_offer(offer_id, name, *, price_cents=1000, grocer_id="willys"):
    return Offer(offer_id=offer_id, grocer_id=grocer_id, external_id=f"e-{offer_id}",
                 week_key="2026-W34", name=name, price_cents=price_cents,
                 unit="st", valid_from="2026-08-17", valid_to="2026-08-23")


def family(**over):
    base = dict(meal_days=2, persons=4, vegetarian=False,
                allergens=(), budget_tier=None)
    base.update(over)
    return FamilyPrefs(**base)


# ---------------------------------------------------------------- shape & keys


def test_plan_menu_returns_plan_with_week_key_and_days():
    recipes = [make_recipe("Köttbullar")]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1))
    assert isinstance(plan, dict)
    assert plan["week_key"] == "2026-W34"
    assert isinstance(plan["days"], list)
    assert len(plan["days"]) == 1
    day = plan["days"][0]
    assert "date" in day and "dish_id" in day and "used_offer_ids" in day


def test_dish_id_is_recipe_title():
    recipes = [make_recipe("Pannkakor")]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1))
    assert plan["days"][0]["dish_id"] == "Pannkakor"


# ---------------------------------------------------------------- N5 constraints


def test_vegetarian_family_only_gets_vegetarian_dishes():
    recipes = [
        make_recipe("Kyckling", vegetarian=0),
        make_recipe("Linssallad", vegetarian=1),
    ]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1, vegetarian=True))
    assert plan["days"][0]["dish_id"] == "Linssallad"


def test_allergens_exclude_matching_recipes():
    recipes = [
        make_recipe("Korv stroganoff", allergens=["mjölk"]),
        make_recipe("Fiskgratäng", allergens=["mjölk", "fisk"]),
        make_recipe("Kikärtsgryta", allergens=[]),
    ]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1, allergens=["fisk"]))
    chosen = plan["days"][0]["dish_id"]
    assert chosen != "Fiskgratäng"          # contains fisk
    assert chosen in {"Korv stroganoff", "Kikärtsgryta"}


def test_budget_tier_filters_recipes():
    recipes = [
        make_recipe("Pasta carbonara", budget_tier="premium"),
        make_recipe("Pytt i panna", budget_tier="budget"),
        make_recipe("Tacopaj", budget_tier="mid"),
    ]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1, budget_tier="budget"))
    assert plan["days"][0]["dish_id"] == "Pytt i panna"


def test_budget_tier_none_is_no_filter():
    recipes = [
        make_recipe("Pasta carbonara", budget_tier="premium"),
        make_recipe("Pytt i panna", budget_tier="budget"),
    ]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1, budget_tier=None))
    # both are allowed; deterministic selection picks one of them
    assert plan["days"][0]["dish_id"] in {"Pasta carbonara", "Pytt i panna"}


def test_maltidsantal_controls_number_of_days():
    recipes = [make_recipe(f"Rätt {i}") for i in range(4)]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=3))
    assert len(plan["days"]) == 3


def test_personer_require_recipe_with_enough_servings():
    recipes = [
        make_recipe("Små portioner", servings=2),
        make_recipe("Familjepanna", servings=6),
    ]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1, persons=6))
    assert plan["days"][0]["dish_id"] == "Familjepanna"


# ---------------------------------------------------------------- offer matching


def test_assigns_matching_offers_to_days():
    recipes = [make_recipe("Köttbullar")]
    offers = [make_offer(10, "Köttfärs 500g"), make_offer(11, "Köttbullar familj"),
              make_offer(12, "Banankartong")]
    plan = plan_menu("2026-W34", offers, recipes, family(meal_days=1))
    used = set(plan["days"][0]["used_offer_ids"])
    assert 11 in used          # title contains ingredient-ish match
    assert 12 not in used      # unrelated offer is not attached


def test_maximizes_offer_hits_across_week():
    # 'Kyckling' matches one offer; 'Fiskgratäng' matches two -> planner should
    # pick the recipe with the greater number of matching offers first.
    recipes = [
        make_recipe("Kyckling med ris"),
        make_recipe("Fiskgratäng med potatis"),
    ]
    offers = [
        make_offer(1, "Kyckling", price_cents=9900),
        make_offer(2, "Fiskgratäng special"),
        make_offer(3, "Fiskgratäng XL"),
    ]
    plan = plan_menu("2026-W34", offers, recipes, family(meal_days=1))
    assert plan["days"][0]["dish_id"] == "Fiskgratäng med potatis"
    assert len(plan["days"][0]["used_offer_ids"]) == 2


def test_no_offer_repeat_across_week():
    recipes = [make_recipe("Köttbullar")]
    offers = [make_offer(20, "Köttbullar familj")]
    plan = plan_menu("2026-W34", offers, recipes, family(meal_days=2))
    all_ids = [oid for d in plan["days"] for oid in d["used_offer_ids"]]
    assert len(all_ids) == len(set(all_ids))


def test_zero_offer_day_degrades_to_recipe_only(caplog):
    import logging
    recipes = [make_recipe("Linssallad")]
    with caplog.at_level(logging.INFO):
        plan = plan_menu("2026-W34", [], recipes, family(meal_days=1))
    assert plan["days"][0]["used_offer_ids"] == []
    assert plan["days"][0]["dish_id"] == "Linssallad"


# ---------------------------------------------------------------- determinism (N7)


def test_deterministic_same_inputs_same_output():
    recipes = [make_recipe(f"Rätt {i}", budget_tier="mid") for i in range(5)]
    offers = [make_offer(i, f"Produkt {i}") for i in range(5)]
    fam = family(meal_days=4, budget_tier="mid")
    a = plan_menu("2026-W34", offers, recipes, fam, seed=1234)
    b = plan_menu("2026-W34", offers, recipes, fam, seed=1234)
    assert a == b


def test_no_repeat_dish_within_week():
    recipes = [make_recipe(f"Rätt {i}") for i in range(5)]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=5))
    dish_ids = [d["dish_id"] for d in plan["days"]]
    assert len(dish_ids) == len(set(dish_ids))


def test_insufficient_recipes_returns_fewer_days():
    recipes = [make_recipe("Enda rätten")]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=4))
    assert len(plan["days"]) == 1   # degrades gracefully, no crash


def test_recipe_dish_id_must_be_string_key():  # guard: reject int recipe_id leaks
    recipes = [make_recipe("Kyckling")]
    plan = plan_menu("2026-W34", [], recipes, family(meal_days=1))
    assert isinstance(plan["days"][0]["dish_id"], str)
