# T7b — Are Swedish grocery weekly offers rikstäckande or locally varied? (MC 1355.9, parent 1355)

Researched 2026-09-26. All VERIFIED claims were confirmed by direct HTTP fetch this session
(raw HTML/JSON saved under `.tmp/` during the run). Question: matapp plans menus from weekly
offers per CHAIN; the owner wants a future "cart at a chosen physical store" feature. Does
chain-level offer data suffice, or must the model eventually carry store-level prices?

**Bottom line: only Lidl is effectively rikstäckande in practice. ICA is store-priced by
design, Coop officially states offers vary per store, and Willys gates its offers page on a
store selection. Chain-level ingestion is an approximation for 3 of 4 chains.**

---

## 1. ICA — store-priced by design (merchant-owned stores)

- **VERIFIED — ICA is not a centrally priced chain.** Official ICA-gruppen page
  "Prissättning på ICA" (https://www.icagruppen.se/om-ica-gruppen/var-verksamhet/affarsmodell/Prissattning-pa-ica/),
  fetched live this session, states: *"Varje ICA-butik drivs av en fristående handlare som
  själv bestämmer sortiment och priser, och det förklarar varför priset på exakt samma vara
  kan skilja sig mellan olika butiker"* and, under "Bestämmer ICA centralt vad varorna ska
  kosta?", answers *"Nej. Alla butiksägare fattar egna beslut om prissättning."* It also
  states online prices are set per store: *"Priset på varorna i ICA:s nätbutiker sätts av den
  enskilda butiken … priset på en och samma vara kan skilja sig markant beroende på vilken
  butik du väljer att e-handla från."*
- **VERIFIED — the offers page itself has a store dimension.** https://www.ica.se/erbjudanden/
  (fetched live, ~242 KB) renders, before any store is chosen: *"Välj butik för att se våra
  aktuella butikserbjudanden – både stammispriser och andra unika erbjudanden"* and later
  *"Välj butik för att ta del av butiksunika erbjudanden och stammispriser."* I.e. the
  default view is the chain-level campaign set, and a store layer of unique offers +
  Stammis prices exists on top of it.
- **VERIFIED — the `weeklyOffers` payload carries a `stores` field.** Each item in
  `window.__INITIAL_DATA__` → `weeklyOffers` has a `"stores":undefined` key (observed on all
  11 sampled items with no store selected). The schema therefore has a per-offer store
  dimension that is populated once a store is chosen; the no-store view leaves it unset.
  (Field observed this session; what values it takes per store is UNVERIFIED — store
  selection happens client-side and was not captured.)
- **VERIFIED — member pricing is personal, not uniform.** Same ICA-gruppen page: *"ICA
  Stammis … ger personliga erbjudanden och rabatter baserade på dina köpvanor, vilket i
  praktiken innebär att det faktiska priset du betalar kan vara lägre än hyllpriset."*
  Stammis offers are per customer; store-unique offers ("butiksunika erbjudanden") are per
  store. Both layers sit on top of the national campaign set.
- **Implication:** ICA chain-level data is only the national campaign subset. A per-store
  cart for ICA **requires store-level data** (and, for full fidelity, member-level Stammis
  data, which is out of scope for a shared planner).

## 2. Willys (Axfood) — per-store offers page, centrally owned chain

- **VERIFIED — the offers page is store-gated.** https://www.willys.se/erbjudanden
  (fetched live, ~205 KB) meta description: *"Läs veckans erbjudanden från respektive butik
  och få unika erbjudanden på produkter du handlar ofta."* The page and
  https://www.willys.se/erbjudanden/butik both render *"Välj butik för att se rätt
  erbjudanden och reklamblad"* — offers and the leaflets ("reklamblad") are selected per
  store.
- **VERIFIED — Willys and Hemköp are separate chains with separate programs.** Willys runs
  Willys Plus (terms: https://www.willys.se/artikel/kundservice/villkor-for-willys-plus,
  fetched live: *"Willys Plus är vårt … kostnadsfria digitala lojalitetsprogram"*); Hemköp
  runs Klubb Hemköp with "Klubbpris" member prices (https://www.hemkop.se/artikel/klubb-hemkop;
  https://hemkop.imbox.wiki/category/174/article/1997: *"Märkningen 'Klubbpris' visas när en
  produkt har ett medlemspris. Medlemspriset gäller för de som är medlemmar i Klubb
  Hemköp"*). A Willys campaign cannot be assumed valid at Hemköp or vice versa.
- **UNVERIFIED — whether Willys member prices ("Medlemspris") are identical across all
  Willys stores.** No official statement was found either way. The Willys Plus terms
  describe *"personligt anpassad köpupplevelse med relevanta erbjudanden"* (personalized
  offers), which suggests at least part of the member offer set is per customer, not per
  store. Willys is an Axfood-owned chain (centrally run, unlike ICA), so base prices are
  plausibly uniform — INFERRED, not verified. Decisive check would be comparing the same
  article's price at two Willys stores via the SPA's OCC API (needs a devtools capture; see
  T2 §2).
- **Implication:** Willys needs **store-level offer data** for a per-store cart (the site's
  own UX says offers are per store); member-price uniformity is unresolved.

## 3. Coop — officially: offers vary between stores and e-commerce

- **VERIFIED — official helpcenter statement.** Coop kundservice article "Aktuella
  erbjudanden, kampanjpriser och medlemspriser"
  (https://kundservice.coop.se/hc/sv/articles/360016692059, fetched via the Zendesk
  Help Center API this session; the HTML page is Cloudflare-gated): *"Erbjudanden kan
  variera mellan butiker och e-handel. Om du saknar ett erbjudande som du sett i ett
  reklamblad kan det vara kopplat till en specifik fysisk butik."* That is Coop's own
  statement that campaigns are not uniform across stores.
- **VERIFIED — the offers entry point is store-first.** https://www.coop.se/butiker-erbjudanden/
  (fetched live): page headline *"Hitta din butiks bästa erbjudanden"*, text *"Se öppettider
  och ta del av din butiks bästa erbjudanden"*; the e-handel config requires postnummer
  before showing assortment (*"För att kunna visa rätt sortiment och varor behöver vi ditt
  postnummer"*) and warns *"Den valda butiken kan ha ett annat sortiment än din tidigare."*
- **VERIFIED — the offers API is store-scoped by design.** The page embeds the offers
  service `dkeUrl: https://external.api.coop.se/dke/offers/` (with key) and a store service
  `storeApiUrl: https://proxy.api.coop.se/external/store/` — the same keys T2 §3 verified
  are accepted by the APIM gateway. The offers service is consumed per chosen store
  (client-side); exact resource paths remain UNVERIFIED (needs a devtools capture).
- **VERIFIED — member prices are store-page-scoped.** Coop helpcenter "Medlemspriser"
  (https://kundservice.coop.se/hc/sv/articles/360013388659, fetched via API): *"Som medlem i
  vårt medlemsprogram Ditt Coop får du varje vecka lägre priser på utvalda varor i våra
  butiker. Rabatten laddas automatiskt på ditt Coop-kort…"* and "Så hittar du dina
  erbjudanden: Coop.se – Logga in och gå till **din butikssida**. Coop-appen – Under fliken
  **Butik**." Member offers are presented per store. Coop's regional structure is real:
  the membership fee *"går till din lokala konsumentförening och gör dig till delägare"*
  (same article) — stores are owned by regional associations, which is the structural
  background for local variation.
- **Implication:** Coop needs **store-level offer data** for a per-store cart; Coop's own
  helpcenter says so explicitly.

## 4. Lidl Sweden — nationally priced in practice; "regions" are warehouse regions

- **VERIFIED — the campaign payload has a region dimension, and it is uniform in the
  observed data.** Campaign page https://www.lidl.se/c/lidl-plus-erbjudanden/a10103637
  (fetched live, ~569 KB): every product carries `"regions":[1,2,3,4,5,6,7]` and a
  `regionsPrices` map. In all 32 products on this page, `regionsPrices` has exactly ONE key
  (`"1"`) — one price for all regions. The `regionsV2` block names the regions:
  **"Halmstad 1", "Halmstad 2", "Halmstad 3", "Rosersberg 1", "Rosersberg 2",
  "Rosersberg 3", "Örebro"** — these are Lidl's distribution-centre regions, not
  customer-facing sales regions, and all seven map to `regionPriceId:"1"`.
- **VERIFIED — Lidl Plus (member) offers ride the same structure.** The observed prices are
  `currentLidlPlusPrice` (e.g. Bananer 14.90 kr, deletedPrice 18.8, "-20%", endDate
  2026-10-04) with `lidlPlusText:"Med Lidl Plus"` — the Lidl Plus campaign prices are in the
  same public payload, keyed by the same single region price id. Lidl Plus coupons beyond
  these are account-gated (T2 §4).
- **INFERRED — Lidl is centrally/nationally priced.** Lidl Sweden operates a hard-discount
  model with central pricing; the observed payload (one region price id across all seven DC
  regions) is consistent with that. The schema *allows* regional price differences, so this
  should be re-checked per campaign at ingestion time rather than assumed forever.
- **Implication:** Lidl is the one chain where **chain-level data is correct today**; the
  ingestion should still assert "all regionsPrices equal" and flag any future divergence.

## 5. Implications for the per-store cart feature

| Grocer | Offers uniform across stores? | Store-level data needed for per-store cart? |
|---|---|---|
| ICA | **No** — stores set their own prices (official); store-unique offers + Stammis layer on top | **Yes** |
| Willys | **No** — offers page is store-gated ("erbjudanden från respektive butik") | **Yes** |
| Coop | **No** — official: "Erbjudanden kan variera mellan butiker och e-handel" | **Yes** |
| Lidl | **Yes in practice** — one region price id across all 7 DC regions in observed data | **No today** (assert-and-flag at ingestion) |

- The planned data model should carry an **optional store dimension from day one**
  (offer → store_id nullable), even though the first ingestion is chain-level. ICA's
  `weeklyOffers[].stores` field and Coop's store-scoped dke API show all three non-Lidl
  chains can eventually populate it.
- Postnummer/city store lookup is supported natively by Coop (`proxy.api.coop.se/external/store/`)
  and by each chain's store pages; ICA and Willys both gate offers on an explicit store
  choice, so a "choose your store" step matches the grocers' own UX.
- Member pricing is a separate axis from geography: ICA Stammis is personal (official),
  Willys Plus offers are described as personalized, Coop member offers are shown on "din
  butikssida". A per-store cart should model member prices as a *user-scoped overlay*, not
  bake them into the shared offer table.
- Open items: (a) Willys member-price uniformity UNVERIFIED; (b) exact Coop dke/Willys OCC
  resource paths still need a devtools capture (T2 open item); (c) Lidl region uniformity
  should be asserted per campaign, not assumed.

# VERDICT: PASS
