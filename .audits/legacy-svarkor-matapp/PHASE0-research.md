# PHASE-0 RESEARCH — matapp framtidsvision (MC 1110 / kort 1110.1)

**Seat:** artemis (vm105) · **Datum (UTC):** 2026-09-07 · **Kort:** 1110.1 (PHASE-0 research)
**Deliverable:** denna fil + `kb remember` (destillerat, engelska, kompakt).

## Sammanfattning av DoD
Varje påstående nedan är märkt med citation-discipline-taggen (VERIFIED / PLAUSIBLE-UNCHECKED /
UNVERIFIED / ASSUMED). Frågorna 1–5 från briefen (`/srv/workspace/svarkor-matapp/briefs/p0-research.txt`)
besvaras var för sig. Slutsats upptill, detaljer + citeringar under.

---

## KORT SVAR per forskningsfråga

**Q1 — Meny-optimering/matplanering under villkor (budget + portioner):**
Prior art är stark och mogen: klassiska **linjärprogrammerings-dietformen** (Stigler 1945) →
moderna **cost-minimizing LP/MILP**-applikationer för måltidssammansättning. Vår motor är idag en
**greedy**-heuristik (rangordna recept efter antal offertträffar); budget/portioner hanteras som
**hårda filter** (N5). För "budget + portioner + majoritet extrapris" räcker sannolikt en
**fördjupad greedy/kontexterad optimering**; MILP är möjligt men kräver en optimizer-dependency
(Gurobi=kommersiell, PuLP/ortools öppen) — ett closure-beslut för arkitektur-kortet, inte en
forskningssjälvklarhet.

**Q2 — "Majoritet ingredienser från extrapris":**
Ingen direkt prior art hittad som *formulerar exakt denna* ratio-optimering. Mekaniskt finns
tre välkända mönster att välja/rena mellan:
1. **Ratio-konstraint** — kräv att ≥ X% av varje recepts ingredienser (eller ≥ X% av veckans
   ingredienser) matchar en vecko-offert i vald butik; välj recept som klarar tröskeln (hård constraint).
2. **Objective-maximering (coverage)** — maximera antalet/andelen ingredienser (eller sparpengar)
   från offerter under budget; greedy/set-cover/knapsack-familjen. **Detta är vad POC-greedyn gör,**
   men idag *utan* explicit "majoritet"-tröskel och *utan* rabatt-storlek.
3. **MILP med ratio + budget + portions-binärer ihop** — mest uttrycksfull, tyngst.
Rekommendation (ASSUMED, grundad i Q1/Q4): definiera "extrapris-ingrediens" entydigt, mät
**andel matchande ingredienser per recept**, tillämpa en **konfigurerbar ratio-tröskel (default ≥50%)**
som hårt villkor, och rangordna/optimera därefter på sparbelopp snarare än bara antal träffar.

**Q3 — Auth för liten lokal web-app:**
OWASP-styrt: **Argon2id** för lösenords-hashing (lägst 19 MiB / iter=2 / p=1), **server-sidig
session** (opak session-ID-cookie, HttpOnly+Secure+SameSite) för en same-origin FastAPI-app.
JWT är *inte* proportionerligt här (inga microservices/cross-origin-tokenbehov; JWT-revokering
är svårare). Ingen egen krypto — använd bibliotek.

**Q4 — Reklamblad/extrapris-data + mätbarhet:**
Återanvänd 164.1 (VERIFIED): Willys/City Gross öppna JSON, ICA/Coop token-styrda, Matpriskollen
normaliserande öppen API. **Live-verifierat denna exekvering:** Willys feed bär BÅDE
offerter-pris (`price.value=49.9`) OCH referenspris (`comparePrice:"71,29 kr"`,
`lowestHistoricalPrice.value=66.9`, `conditionLabel:"Spara 17,00 kr/st"`) → **rabatt-storlek är
representerbar vid källan**. POC-offert-schemat sparar dock **inte** referenspris (endast
`price_cents`) → "extrapris" mäts idag som *närvaro-av-offert*, inte *rabatt-storlek*. För att
mäta "majoritet extrapris" robust: persistera referenspris + matcha per ingrediens + beräkna andel.

**Q5 — Publicerade benchmarks/parametrar för meny-optimering:**
**UNVERIFIED.** Ingen publicerad benchmark hittad för specifikt "majoritet-extrapris-veckomeny"
(skulle vara produktens egen DoD-mätning). Optimeringslitteraturen (LP-diet) ger ramverket men
inga produktionsparametrar för detta krav.

---

## Q1 — Meny-optimering / matplanering under villkor: algoritmer & prior art

### Prior art (linjärprogrammering / cost-minimizing diet)
- **[VERIFIED] Stigler diet (klassisk LP-fundament).**
  Källa: https://en.wikipedia.org/wiki/Stigler_diet
  Citat: *"The Stigler diet question is a **linear programming** problem… the diet question
  originally asked in what quantities a 154-pound (70 kg) male would have to consume 77 different
  foods in order to fulfill the recommended intake of 9 different nutrients while keeping expenses
  at a minimum."* — detta är ursprunget till "billigaste möjliga meny under näringsbivillkor".
- **[VERIFIED] "Linear Optimization for the Perfect Meal: A Data-Driven Approach to Optimising
  the Perfect Meal Using Gurobi" (2025, arXiv 2501.04143).**
  Källa: https://arxiv.org/abs/2501.04143
  Citat (abstrakt): *"This study aims to optimize meal planning for nutritional health and cost
  efficiency using linear programming… our model minimizes meal costs while meeting specific
  nutritional requirements."* Visar att cost-minimizing måltids-LP är aktiv, publicerad prior art.
- **[VERIFIED] "Smart Grocery Shopping: a Utility-Based Mathematical Framework and Optimal
  Strategies" (IEEE SMC 2025, DOI 10.1109/smc58881.2025.11343611).**
  Källa (metadata): https://api.crossref.org/works?query.bibliographic=Smart+Grocery+Shopping
  Existerar som IEEE-konferenspapper 2025; **innehåll om just offerter/rabatter
  [PLAUSIBLE-UNCHECKED]** — abstrakt ej hämtningsbart här (IEEE bakom inloggning). Ledtråd för
  arkitekt-kortet att kolla: utility-framework kan vara relevant för att vikta extrapris-värde.

### Hur vår motor gör det idag (VERIFIED — källkod läst denna exekvering)
- `/srv/workspace/svarkor-matapp-root-route/dobbie/922.1-root-route-src-20260903/src/planner/menu.py`
  `plan_menu(...)`: filtrerar recept på N5 (vegetarian, allergener, budget_tier, servings>persons),
  sedan **greedy**: rangordna efter `_offer_hit_count` (antal offert-träffar mot receptet) DESC, tilldela
  en rätt/veckodag, aldrig upprepa rätt. Deterministisk (`random.Random(seed=1234)`).
- `app/routers/menu.py`: HTTP-tunnlare → `FamilyPrefs(meal_days, persons, vegetarian, allergens,
  budget_tier)` → `plan_menu(...)`. Budget är idag en **tier** (budget|mid|premium), INTE en
  explicit kron-budget (se Q2 gap).
- Slutsats Q1: vår nuvarande motor = greedy coverage-heuristik under hårda N5-filter. Detta är en
  legitim, deterministisk metod för prototyp-storlek. Om "3 veckomenyförslag med majoritet
  extrapris" kräver *variation mellan förslagen* → seeds/flera greedy-körningar eller
  MILP-objektiv ger det. UNVERIFIED om det behövs optimalitetsgaranti.

## Q2 — "Majoritet ingredienser från extrapris": hur säkerställs motoriskt?

### Definition "extrapris-ingrediens" (ASSUMED, från Q4-data)
En ingrediens i ett recept = **extrapris** i vald butiks vecka om dess namntoken matchar en
offert i den butikens vecko-offertset (POC-metoden) — eller, starkare (kräver referenspris i DB),
om offertens rabatt > 0 (sparad krona).

### Mönster A — Ratio-konstraint (rekommenderat default)
Kräv `andelen_matchnande_ingredienser >= tröskel` (t.ex. 0.5) som **hårt filter** i N5-steget
(före greedy/MILP). Recept som inte når tröskeln ratas. Detta gör "majoritet" **explicit och
mätbar** — en tydlig förbättring över dagens greedy som maximerar träffar men aldrig garanterar
"majoritet" per rätt. Mätning: `count(ingridienser matchar offerter) / count(ingridienser)` per recept.

### Mönster B — Optimering (coverage / knapsack)
Maximera `Σ sparbelopp` eller `Σ extrapris-ingredienser` över veckans rätter under budget/portioner.
Greedy (nuvarande) = snabb approximation; set-cover / weighted-knapsack = exaktare. Inga nya
bibliotek krävs för greedy; MILP (PuLP/ortools/Gurobi) om exakt optimering önskas.

### Direkt prior art för just denna ratio-formulering
- **[UNVERIFIED]** Ingen publicerad källa hittad som formulerar "majoritet av veckomenyns
  ingredienser från varukorgens erbjudanden" som exakt samma mål. IEEE SMC 2025-pappret ovan är
  närmast men innehållet ej verifierat. → Märk: ingen etablerad benchmark/standard för detta krav;
  det är produktens egen definition. (Återbruk: 164.1 tydliggör att offerterna finns maskinläsbart;
  "majoritet" är vår mätregel, inte en extern standard.)

## Q3 — Auth för liten lokal web-app (session vs JWT, hashing)

### Lösenords-hashing — OWASP (VERIFIED)
- **[VERIFIED] OWASP Password Storage Cheat Sheet.**
  Källa: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
  Citat: *"Passwords should never be stored in plain text. Instead, they must be protected using
  strong, slow hashing algorithms such as Argon2id, bcrypt, or PBKDF2."* och *"Use Argon2id with a
  minimum configuration of 19 MiB of memory, an iteration count of 2, and 1 degree of
  parallelism."* → Argon2id är förstahandsval; bcrypt (wf≥10) acceptabelt fallback.
  Python: `argon2-cffi` / `passlib` — använd bibliotek, aldrig egen krypto.

### Session vs JWT — OWASP ramverk (VERIFIED) + proportionerligt val (ASSUMED)
- **[VERIFIED] OWASP Session Management Cheat Sheet.**
  Källa: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
  Citat: *"Once an authenticated session has been established, the session ID (or token) is
  temporarily equivalent to the strongest authentication method… The session ID or token binds the
  user authentication credentials… to the user HTTP traffic."* → session-ID-token är standardramverket.
- **[ASSUMED] proportionerligt val för matapp:** enda same-origin FastAPI-tjänst (server-rendered +
  statisk JS-frontend, som POC idag) → **opak server-sidig session-cookie** (HttpOnly, Secure,
  SameSite=Lax eller Strict; slumpad session-ID; serverd-ssid→user-mappning i DB) är proportionerligt
  och enklare att återkalla än JWT. JWT (stateless bearer) motiveras främst av
  microservices/cross-origin/mobiltoken-behov — inget av dem gäller här. Detta är en rekommendation för
  arkitektur-kortet.

## Q4 — Reklamblad/extrapris-data + hur "majoritet extrapris" mäts

### Återanvändning av 164.1 (fleet prior art — VERIFIED 2026-08-20, ref i workspace)
`/srv/workspace/svarkor-kvallsmat-recept/artemis/164.1-offers-machine-readable-20260820.md`
| Kedja | Form | Auth | Nivå (164.1) |
|---|---|---|---|
| Willys | Öppen REST-JSON (Axfood) | Nej | Låg — VERIFIED |
| City Gross | Öppen REST-JSON (Loop54) | Nej | Låg — VERIFIED |
| Hemköp | Axfood REST-JSON (som Willys) | Nej | Låg–Medel — PLAUSIBLE-UNCHECKED (re-verifiera) |
| Lidl | JSON i HTML (data-grid-data) + gridboxes | Nej | Medel |
| ICA | REST-JSON offerreader | Ja (APIM-token) | Medel–Hög |
| Coop | REST-JSON dke/offers | Ja (sub-key) | Medel–Hög |
| Matpriskollen | `matpriskollen.se/api/v1/stores/{id}/offers` — öppen, normaliserad | Nej | Låg (3:e part) |

### LIVE-verifiering denna exekvering (2026-09-07) — Willys bär referenspris (rabatt-storlek)
```
$ curl -s "https://www.willys.se/axfood/rest/v1/search/campaigns/online?q=2110&type=PERSONAL_GENERAL&page=0&size=2" ...
{"potentialPromotions":[{"conditionLabel":"Spara 17,00 kr/st","rewardLabel":"49,90/st",
 "comparePrice":"71,29 kr", "price":{"currencyIso":"SEK","value":49.9},
 "lowestHistoricalPrice":{"currencyIso":"SEK","value":66.9}, ...}]}
```
→ **[VERIFIED]** källan representerar alltså BÅDE offertpris (49,90) OCH jämförelse/referenspris
(71,29) + historiskt lägsta (66,90) + "spara X kr/st". Dvs **rabatt-storlek ÄR mätbar vid källan**
för Willys (den kedja som är lättast att bygga på).

### Gap i nuvarande POC-offert-schema (VERIFIED — källkod läst)
- `src/offers_db/store.py` `Offer`: endast `price_cents`, `unit`, `name`, `external_id`, vecko-fält.
  **Ingen** `regular_price_cents` / `original` / `savings` kolumn. `grep` över `src/`+`app/` för
  `regular|original|was_price|ordinary|currentPrice|deletedPrice` → **0 träffar**.
- Konsekvens: idag är "extrapris" = *närvaro av offert* (token-match offert-namn ↔ ingrediens-namn),
  inte *rabatt-storlek*. För den hårda "majoritet" — och för att "majoritet av ingredienserna
  kommer från extrapriser" ska vara *verifierbar* — krävs: (a) persistera referenspris + sparbelopp
  i offert-/receptmognad, (b) per-ingrediens-flagga "denna ingrediens är på extrapris i butik X i
  vecka W", (c) aggregat: andel extrapris-ingredienser per rätt + per vecka. (Arkitektur-beslut för
  bernie/map-kortet.)

## Q5 — Publicerade benchmarks/parametrar för meny-optimering

- **[UNVERIFIED]** Ingen publicerad benchmark hittad som definierar en standardmätning för
  "majoritet-extrapris-veckomeny" (lägsta andel, sparad krona per meny, tid att generera 3 förslag).
  Optimeringslitteraturen (LP-diet, Q1) ger ramverket men INGA färdiga produktionsparametrar för
  just detta krav.
- Slutsats: produktens egna DoD-mätning måste definieras (t.ex. "≥50% av ingredienserna per förslag
  på extrapris", "minska menysumman X% mot referenspris" — hämtbart tack vare Q4:s referenspris hos
  Willys). Inga externa siffror att citera → inga fabricerade.

---

## Risker / öppna frågor för efterföljande kort (map/plan/DA)
1. **Optimizer-dependency (MILP vs greedy):** greedy (nuvarande) = inget nytt bibliotek, deterministisk,
   tillräcklig för prototyp. MILP (PuLP/ortools/Gurobi) = exaktare men ny extern dependency +
   licensfråga (Gurobi kommersiell). Beslut hör till closure-kartan.
2. **Referenspris-persistens:** för att mäta "majoritet"/sparbelopp krävs ny kolumn + matchning —
   saknas idag (Q4-gap).
3. **POC-butiksändpoints:** POC konfigurerar `feeds.ica.se/week`, `feeds.coop.se/week`,
   `feeds.willys.se/week` (app/config.py). 164.1 visar ICA/Coop är token-gated; dessa placeholder-
   feeds faktiska funktion måste verifieras av map/plan — [PLAUSIBLE-UNCHECKED] denna exekvering.
4. **Tre förslag kontra determinism:** nuvarande motor ger ett deterministiskt svar per (seed). Tre
   *olika* förslag kräver antingen 3 seeds (deterministiskt reproducerbart) eller variationsmål — ett
   planeringsbeslut.
5. **Datakällans ToS/robots:** Willys/City Gross öppna, men återanvändning i kommersiell tjänst bör
   kontrolleras mot kedjornas villkor (164.1 varning) — juridisk-risk-notering, ej block.

---

## Metod & verifieringsnivå
- **VERIFIED** = hämtad/läst DENNA exekvering (curl / arXiv-API / Crossref / OWASP-sida / källkod) och
  text/status stödjer påståendet (citat inkluderat).
- **PLAUSIBLE-UNCHECKED** = gick inte att fullt verifiera (IEEE-betald, POC-feed-status).
- **UNVERIFIED** = ingen källa funnen (Q5).
- **ASSUMED** = egen slutledning/rekommendation, märkt som sådan.
- **Återanvändning** enligt reuse-research-gate: 164.1 (svarkor-kvallsmat-recept) är fleet prior art
  för Q4 och citeras som sådan; POC-källkoden läst direkt.

VERIFY_EXIT=0
