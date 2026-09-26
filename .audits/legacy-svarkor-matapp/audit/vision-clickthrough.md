# MC 1188.7 — Vision click-through audit: varje klick, varje länk (matapp)

Live site: https://sibbamala.com/matapp/ (POC state, revert 12e2e30)
Audit date: 2026-09-13 (UTC). Auditor: bernie (general agent).
Method: Playwright headless Chromium 151 (real browser, real clicks, console + network capture),
plus curl for raw API probes and WCAG contrast math. Screenshots in this directory
(shot1–shot8). Every claim below is tagged VERIFIED (command/tool run this audit) or BLOCKED.

**Vision-LLM caveat (BLOCKED):** the `vision_analyze` tool timed out 7/7 times this session,
so the "look at the screenshot with eyes" pass was replaced by (a) programmatic pixel/overflow
analysis of the screenshots and (b) WCAG contrast math on the actual CSS tokens. The
screenshots are saved here so a human or a later vision-capable pass can review them.

---

## 1. Console on load — PASS

VERIFIED (Playwright, `audit_run.py`): navigation to /matapp/ produced
- console messages: **none**
- page errors (uncaught exceptions): **none**
- failed requests (>=400) on load: **none**
- all 7 referenced assets (3 CSS + 4 JS, cache-busted) returned HTTP 200 (curl, VERIFIED).

`node --check` on all four JS files: no syntax errors (VERIFIED).

## 2. Click-through log — every interactive element

All clicks run in a real headless browser; "new console" = console messages emitted by that click.

| # | Element | Action | Result | Console |
|---|---------|--------|--------|---------|
| 1 | nav "Butiker" | click | OK — stores view shown, menu hidden | none |
| 2 | nav "Veckomeny" | click | OK — menu view shown, stores hidden | none |
| 3 | store checkbox willys | check | OK — card highlights, hint "1/3 valda." | none |
| 4 | store checkbox ica | check | OK | none |
| 5 | store checkbox coop | check | OK — hint "3/3 valda — max 3 butiker." | none |
| 6 | "Spara urval" (submit) | click | OK — POST /api/stores/select 200, hint "Sparat: 3 butiker valda." | none |
| 7 | menu form: week/meal_days/persons/budget/vegetarian/allergens/seed | fill/select | OK | none |
| 8 | "Hämta veckomeny" (valid week) | click | OK — 5 day cards rendered, header "Vecka 2026-W37", "5 middagar" | none |
| 9 | "Hämta veckomeny" (empty week) | click | OK — specific error "Ange en vecka, t.ex. 2026-W34." | none |
| 10 | "Hämta veckomeny" (week="banana") | click | OK — error banner shown with generic text; 422 in console (expected) | 422 + handled Error (see finding F1) |
| 11 | "Försök igen" (menu-retry) | click | OK — resubmits; with week still invalid it re-errors (correct behavior) | 422 (expected) |
| 12 | "Försök igen" (stores-retry) | click | OK — reloads stores, error banner hidden | none |

VERIFIED via `audit_run.py` output (full transcript preserved in evidence section below).

## 3. Link inventory + HTTP codes

The page has exactly 5 href targets (VERIFIED, curl + grep of live HTML):

| Target | Type | HTTP |
|---|---|---|
| `#` (nav Butiker) | JS-handled tab, no navigation | n/a |
| `#` (nav Veckomeny) | JS-handled tab, no navigation | n/a |
| static/css/base.css?v=1e554f53 | stylesheet | 200 |
| static/css/components.css?v=1273106d | stylesheet | 200 |
| static/css/responsive.css?v=d24ae63c | stylesheet | 200 |

Also VERIFIED 200: favicon.ico, robots.txt, all 4 JS files.
**No dead links found.** No external links exist on the page at all.

## 4. API behavior (curl, VERIFIED)

| Probe | Result |
|---|---|
| GET /api/stores | 200, 3 stores (willys, ica, coop) |
| GET /api/stores/selected | 200 |
| POST /api/stores/select {3 ids} | 200 `{"selected":[...]}` |
| POST /api/stores/select {4 ids} | 422 "at most 3 stores can be selected" |
| POST /api/stores/select unknown id | 422 "unknown store_id(s)" |
| POST /api/stores/select {} or [] | 200 `{"selected":[]}` |
| GET /api/menu (no params) | 422 "Field required" (week) |
| GET /api/menu?week=banana | 422 pattern mismatch |
| GET /api/menu?week=2026-W37&... | 200, 5 days |
| meal_days=0 / -1 / 15 | 422 (bounds 1–14) |
| persons=99 | 422 (max 10) |
| budget_tier=bogus | 422 pattern |
| seed=abc | 422 int parse; seed=-5 accepted (200) |
| week=2026-W99 / W0 | 200 — dates resolve to 2027-11 / 2025-12 (no calendar validation) |
| allergens=bogus | **200 — silently ignored** (no enum validation) |
| menu with NO stores selected | 200 — menu generates anyway (no store requirement server-side) |
| GET /api/ , /api/docs, /api/openapi.json | 404 (docs not exposed — good) |

Site state restored after testing: selection reset to `["willys"]` (the state found at audit start). VERIFIED via GET /api/stores/selected after reset.

## 5. Vision findings per view

### 5.1 Start view (stores) — shot1/shot3/shot6
- VERIFIED (WCAG math on live CSS tokens): all measured text pairs pass AA. Header title 5.78:1,
  subtitle 5.11:1, body 13.38:1, muted text 4.71:1 (on white) / 4.50:1 (on surface-alt — exactly
  at the AA threshold, passes), error text 4.64:1, footer 10.85:1.
- VERIFIED (pixel analysis): no content pixels clipped at content-area edges; palette consistent
  (tomato red #b73a1a header/buttons, cream background, green accent for selected cards).
- VERIFIED (browser overflow check at 360px): 0 overflowing/clipped elements, no horizontal scroll.

### 5.2 Menu generated — shot4/shot7
- VERIFIED: 5 day cards render with date, Swedish weekday, dish name, offers section.
- VERIFIED (WCAG): offer badge green-on-green 5.50:1 AA-pass; zero-offer badge muted-on-grey
  **4.26:1 — passes AA only as large text; at 12px normal weight it is below the 4.5:1 AA-normal
  threshold** → finding F2.
- VERIFIED: 0-offer days degrade correctly to "Inga erbjudanden" chip (REV2 R4 behavior confirmed live).
- Note (VERIFIED): `--color-success-700` token is referenced in components.css:266 but never
  defined in base.css; the hardcoded fallback #1c6d36 is what renders. Fragile, currently correct.

### 5.3 Error view — shot5
- VERIFIED: error banner (red border/bg) renders, retry button present, focus-visible outlines
  defined globally (2px solid, offset 2).

### 5.4 Narrow viewport (SPEC: owner tests on phone)
- **360px (VERIFIED, browser overflow check): clean.** No horizontal overflow, no clipped text,
  single-column grids, allergens multi-select 280×133px, all tap targets ≥20px.
- **320px (VERIFIED): day cards overflow the viewport by ~40px** (card right edge = 320 = docW,
  but .menu-grid scrollWidth 280 vs clientWidth 240 → cards poke under the right padding edge).
  320px is below the spec'd phone width, so this is a minor finding (F3), not a blocker.
- BLOCKED: subjective aesthetics (does it *look* good?) — no vision-LLM available this session;
  screenshots shot1–shot8 are saved in this directory for human review.

## 6. Findings (adversarial)

**F1 — 422 error detail never reaches the user (MEDIUM).**
The API returns precise, actionable 422 details ("String should match pattern
'^\d{4}-W\d{1,2}$'", "at most 3 stores..."), but menu.js/stores.js catch the error and show a
generic Swedish message ("Kunde inte hämta veckomenyn. Kontrollera att du valt butiker och att
veckan är giltig..."). The card asked: "är felmeddelandet begripligt i UI:t eller ser användaren
bara 'error'?" Answer: the user sees a *readable but generic* message — better than raw "error",
worse than surfacing the actual cause. Empty-week is the exception: it has a specific client-side
message. VERIFIED (audit_run.py + grep of menu.js/stores.js: no code reads err.detail).

**F2 — zero-offer badge contrast 4.26:1 (LOW).**
`.offer-badge--zero` is 12px normal-weight muted text on #f2f4f5 → 4.26:1, below AA-normal (4.5:1).
Fix: darken to --color-neutral-600 (#50585d, 6.0:1) or make it bold. VERIFIED (WCAG math).

**F3 — 320px day-card overflow (LOW, below spec width).**
At 320px the menu grid's minmax(280px,1fr) column plus page padding exceeds the viewport;
cards extend under the right padding. 360px (the spec'd phone width) is clean. Fix if desired:
minmax(240px,1fr) for the menu grid. VERIFIED (browser overflow check).

**F4 — allergens values not validated server-side (LOW).**
`allergens=bogus` returns 200 and is silently ignored — inconsistent with every other param
which 422s. Not user-visible (UI only offers the 11 real options) but an API-contract wart.
VERIFIED (curl).

**F5 — menu generates with no stores selected (INFO).**
Fresh session + GET /api/menu → 200 with dishes. The UI text implies stores are required
("Kontrollera att du valt butiker"), but the API doesn't require them. POC-acceptable;
flag for the goal-vs-state diff. VERIFIED (curl with fresh cookie jar).

**F6 — week W0/W99 accepted (INFO).**
Pattern `^\d{4}-W\d{1,2}$` allows W0 and W99; the API happily generates menus for
2025-12-22 (W0) and 2027-11-15 (W99). No crash, no error — just semantically odd weeks.
VERIFIED (curl).

**F7 — `--color-success-700` token missing (INFO).**
components.css:266 references a token that base.css never defines; the fallback constant
carries the color. Works today, breaks silently if someone reorders the var. VERIFIED (grep).

## 7. Evidence

- Click-through transcript: this file §2 (from `audit_run.py`, Playwright Chromium 151 headless).
- API probes: §4 (curl against live site, 2026-09-13).
- Contrast math: §5 (WCAG relative-luminance formula on tokens from live base.css/components.css).
- Overflow/clipping: browser `getBoundingClientRect` sweep at 1280/375/360/320px (overflow_check.py, clip320.py).
- Screenshots: shot1–shot8 in this directory (desktop + 360px + 320px, all major states).
- node --check on all 4 JS files: pass.

VERIFY_EXIT=0
