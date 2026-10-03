"""app.services.shopping_text — PURE shopping-text algorithms (MC 10037 P1-b).

Ported verbatim-in-behaviour from matapp ``shopping.py`` (the hard-won bug fixes
of GT-1e live here, not in the HTTP layer):

  * ``normalize_item_name``  — dedup key: lower-case, strip parentheticals,
    strip leading colour/state adjectives, apply the synonym map.
  * ``guess_category``       — keyword map, LONGEST-KEYWORD-FIRST (sorted once
    at import) so "tomatpuré" lands in torrvaror, never the shorter "tomat"
    in frukt/grönt.
  * ``combine_quantities``   — same-unit merge ("400 g"+"200 g" -> "600 g"),
    else " + " fallback.

PURE BY CONSTRUCTION (the DA lesson from matapp rank-3: build_shopping_list
imports db inside itself for pantry lookup — never here). The one deliberate
behavioural drop: matapp's pack→grams conversion consulted its ingredient DB
(``db.resolve_pack_to_grams``); with no DB seam by design, pack units fall back
to " + " instead — recorded deviation.
"""
from __future__ import annotations

import re

# Nyckelord för automatisk kategoritilldelning (case-insensitive substring).
# Mer specifika matchningar kommer före generella — se _CATEGORY_KW_SORTED.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "frukt/grönt": [
        "tomat", "lök", "vitlök", "paprika", "zucchini", "broccoli", "blomkål",
        "morot", "rotsak", "potatis", "sötpotatis", "spenat", "sallad", "gurka",
        "äpple", "päron", "banan", "apelsin", "citron", "lime", "avokado",
        "svamp", "majs", "ärtor", "bönor", "linser", "purjolök", "selleri",
        "ingefära", "koriander", "basilika", "persilja", "dill", "timjan",
        "rosmarin", "grönsak", "frukt", "bär", "mango", "ananas",
    ],
    "mejeri": [
        "mjölk", "grädde", "crème fraiche", "creme fraiche", "filmjölk",
        "yoghurt", "smör", "margarin", "ost", "mozzarella", "parmesan",
        "halloumi", "fetaost", "feta", "kvarg", "ägg", "gräddfil",
        "ricotta", "mascarpone", "keso",
    ],
    "kött": [
        "kyckling", "kycklingfilé", "kycklinglår", "kycklingbröst",
        "köttfärs", "malet kött", "biff", "fläsk", "bacon", "skinka",
        "korv", "falukorv", "isterband", "lax", "fisk", "räkor", "tonfisk",
    ],
    "torrvaror": [
        "pasta", "ris", "couscous", "bulgur", "quinoa", "nudlar",
        "mjöl", "socker", "salt", "peppar", "krydda", "olja", "olivolja",
        "rapsolja", "vinäger", "soja", "sojaost", "tomatsås", "tomatpuré",
        "konserv", "burk", "kikärtor", "linser", "bönor", "soppa",
        "buljong", "fond", "ketchup", "senap", "majonnäs", "dressing",
        "honung", "sirap", "vanilj", "bakpulver", "jäst", "ströbröd",
        "havregryn", "müsli", "cornflakes", "knäcke", "bröd", "tortilla",
        "pitabröd", "nötter", "mandlar", "frön", "torkad", "torkade",
    ],
}

# Longest keyword wins: "tomatpuré" (torrvaror) beats "tomat" (frukt/grönt).
_CATEGORY_KW_SORTED = sorted(
    [(kw, cat) for cat, kws in CATEGORY_KEYWORDS.items() for kw in kws],
    key=lambda x: len(x[0]), reverse=True,
)

# Synonym canonicalization (matapp FOOD_SYNONYMS, ported as-is).
FOOD_SYNONYMS = {
    "sal": "salt",
    "papper": "peppar",
    "black pepper": "peppar",
    "lökar": "lök",
    "rödlök": "lök",
    "rödlökar": "lök",
    "isbergssallad": "sallad (isbergs)",
    "röd paprika": "paprika",
    "gul paprika": "paprika",
    "grön paprika": "paprika",
}

_QTY_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZåäöÅÄÖ]*)\s*$")


def guess_category(item_name: str) -> str:
    """Kategori via nyckelordskarta, längsta nyckeln först; annars 'övrigt'."""
    name_lower = item_name.lower()
    for keyword, category in _CATEGORY_KW_SORTED:
        if keyword in name_lower:
            return category
    return "övrigt"


def normalize_item_name(name: str) -> str:
    """Normaliserar ett inköpsnamn till sin dedup-nyckel (matapp GT-1e)."""
    s = name.strip().lower()
    # "rödlök(ar)" → "rödlök"
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    # "röda lökar" → "lökar"  (sedan synonymkarta → "lök")
    s = re.sub(r"^(röd[a]?|vit[a]?|gul[a]?|grön[a]?|halv[a]?|färsk[a]?)\s+",
               "", s).strip()
    return FOOD_SYNONYMS.get(s, s)


def parse_quantity(quantity_str: str) -> tuple[float, str]:
    """'400 g' → (400.0, 'g'); '2 st' → (2.0, 'st'); misslyckat → (0.0, infört)."""
    if not quantity_str:
        return (0.0, "")
    match = _QTY_RE.match(quantity_str.strip())
    if match:
        try:
            return (float(match.group(1).replace(",", ".")),
                    match.group(2).strip())
        except ValueError:
            pass
    return (0.0, quantity_str)


def combine_quantities(q1: str, q2: str) -> str:
    """Samea enhet → summera ('600 g'); annars ' + '-fallback (se modulen ovan)."""
    amount1, unit1 = parse_quantity(q1)
    amount2, unit2 = parse_quantity(q2)
    u1 = unit1.lower()
    u2 = unit2.lower()
    if u1 and u2 and u1 == u2 and amount1 > 0 and amount2 > 0:
        combined = amount1 + amount2
        if combined == int(combined):
            return f"{int(combined)} {unit1}"
        return f"{combined:.1f} {unit1}"
    return " + ".join(p for p in (q1, q2) if p)
