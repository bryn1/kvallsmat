# T2 — Real grocery offer data sources for matapp (MC card 1355.2)

Researched 2026-09-24. All "VERIFIED" claims were confirmed by direct HTTP fetch/curl this
session; "UNVERIFIED" means the lead exists but the decisive check was not run.

## 0. The current fetcher is fictional — confirmed

- `https://feeds.willys.se/week`, `https://feeds.ica.se/week`, `https://feeds.coop.se/week`
  — **VERIFIED**: none of these hostnames resolve in DNS at all
  (`curl: (6) Could not resolve host` for all three). There is no such API family; the
  fetcher can never work against them.

## 1. ICA — best case, data is already in the page

- **Official public API:** No documented public offers API. ICA runs a WSO2 API gateway at
  `https://apim-pub.gw.ica.se/sverige/digx` (external) and
  `https://gw.api.azure.icacorp.net/sverige/digx` (internal) — **VERIFIED** that these
  endpoint names are published in the page state of https://www.ica.se/erbjudanden/
  (`window.__INITIAL_DATA__` → `endpoints`), together with an anonymous `publicAccessToken`.
  Whether the gateway exposes an offers resource without a developer account: **UNVERIFIED**.
- **Working scraping approach — VERIFIED:** `https://www.ica.se/erbjudanden/` (HTTP 200,
  ~242 KB) embeds the **complete weekly offers array server-side** in
  `window.__INITIAL_DATA__` under `weeklyOffers`. Each item carries:
  `id`, `details.brand`, `details.name`, `details.packageInformation` ("420 g"),
  `details.mechanicInfo` ("119 kr/st", "5 för 100 kr"), `validTo` (ISO date),
  `comparisonPrice` ("283:33/kg"), `restriction` ("Max 2 köp/hushåll"),
  `parsedMechanics` (structured: type/benefitType/quantity/unitSign/value1-4),
  `eans[]` (EAN + description + image URL), `category.articleGroupName`.
  Example observed live: Findus Fryst torskryggfilé, 119 kr/st, validTo 2026-09-27, EAN 7310500185927.
  - Caveat: the raw JS object is not strict JSON (contains `undefined` and `new Map([])`
    literals); a small sanitizer (replace `undefined`→`null`, `new Map([...])`→`{}`) makes it
    parseable. Normalization difficulty: **LOW** — the mechanics are already parsed.
- **robots.txt:** https://www.ica.se/robots.txt has no Disallow for `/erbjudanden/`
  (**VERIFIED** — only sitemap lines and unrelated paths in the fetched head).
- **Open-source:** no maintained ICA offers scraper found. GitHub search "ica api sweden"
  returns only a 2020 recipe-generator (https://github.com/ViktorEdman/Random-Recipe-Generator,
  last push 2020 — stale). GitHub "ica scraper erbjudanden": 0 results (**VERIFIED**).

## 2. Willys (Axfood) — real e-com platform, no public offers feed

- **Official public API:** none documented. Willys runs SAP Commerce Cloud (OCC):
  the page bundles reference the OCC base
  `https://ax-int-ccv2-occ-api.ckbzu73q5d-axfoodita3-d1-public.model-t.cc.commerce.ondemand.com`
  and paths `/axfood/rest/v2/...` (**VERIFIED** — strings found in
  `/_next/static/chunks/pages/_app-*.js` on www.willys.se). However:
  - `https://www.willys.se/axfood/rest/v2/willys/products/search?query=mjölk` returns the
    Angular shopping SPA HTML, not JSON, with or without `Accept: application/json`
    (**VERIFIED** — the path is SPA-routed; the real OCC endpoint is not reachable this way).
  - The exact working OCC search/campaign endpoint is **UNVERIFIED**; capturing it needs a
    browser devtools session (the SPA calls it client-side).
- **Offers page:** `https://www.willys.se/erbjudanden` (HTTP 200, ~205 KB) is a Next.js
  `WillysPromotionPage` whose `__NEXT_DATA__` contains only CMS promo-page metadata
  (`willysPromotionsCMSComponent`, `campaignType`) and **no product/price data**
  (**VERIFIED** — parsed the JSON; zero price keys). Offers are loaded client-side.
- **ToS/robots:** https://www.willys.se/robots.txt (**VERIFIED**): `Disallow: /sok`,
  `Crawl-delay: 10`, `Visit-time: 0400-0845 UTC`. Scraping is possible but must be slow and
  night-windowed; the offers page itself is not disallowed.
- **Open-source:** `kaddaGH/willys_scraper` (2019, Ruby) and `AlinGD/Willys-Web-Scraper`
  (2019, Python) exist but are **stale/dead leads** (last push 2019, pre-Next.js site)
  (**VERIFIED** via GitHub API metadata). GitHub "willys api sweden": 0 results.

## 3. Coop — real API gateway, keys published in page source

- **Official public API:** Coop's site embeds its full API config in the HTML of
  https://www.coop.se/butiker-erbjudanden/ (redirect target of /erbjudanden/, **VERIFIED**):
  - `hybrisApiUrl: https://external.api.coop.se/ecommerce` (SAP Hybris OCC behind Azure
    API Management) with `hybrisApiSubscriptionKey` and `hybrisApiVersion: v1`
  - `dkeUrl: https://external.api.coop.se/dke/offers/` with its own `dkeKey` — this is the
    offers ("dke") service
  - `articleServiceApiUrl: https://external.api.coop.se/articleservice` (v1)
  - `storeApiUrl: https://proxy.api.coop.se/external/store/`
- **VERIFIED:** the gateway answers with the subscription keys taken from the page source
  (HTTP 404 `{"statusCode":404,"message":"Resource not found"}` — an APIM auth failure would
  be 401, so the keys are accepted; the exact resource paths under `/ecommerce/v1/...`,
  `/dke/offers/...` and `/articleservice/v1/...` are **UNVERIFIED** — probing common paths
  404'd; the real paths need a devtools capture of handla.coop.se traffic).
- **ToS/robots:** https://www.coop.se/robots.txt disallows `/mitt-coop`, `/handla/sok/*`,
  `/handla/betala` — the offers pages are not disallowed (**VERIFIED**).
- **Open-source:** no Coop Sweden scraper found (GitHub searches returned 0 relevant repos).

## 4. Lidl Sweden — two viable paths, both real

- **Offers page:** `https://www.lidl.se/c/erbjudanden` (HTTP 200, ~394 KB) lists campaign
  tiles linking to campaign pages such as
  `https://www.lidl.se/c/lidl-plus-erbjudanden/a10103637` (**VERIFIED**).
- **Embedded data — VERIFIED:** the campaign page (fetched live, ~569 KB) embeds the full
  product dataset as HTML-escaped JSON inside the page, including per-product
  `regionsPrices` → `currentLidlPlusPrice` → `price.price` (e.g. 14.9), `price.hasVat`,
  `price.endDate` ("2026-10-04T21:59:59Z"), `price.discount.deletedPrice` (18.8),
  `discountText` ("-20%"), plus `title` ("Bananer") and multipack/origin flags.
  Normalization difficulty: **LOW-MEDIUM** — unescape the JSON blob, map
  price/endDate/deletedPrice; unit info is less structured than ICA's.
- **Lidl Plus API (account-gated):** open-source clients exist:
  - https://github.com/zsobix/lidlplus-api — Python, fork of Andre0512/lidl-plus, last
    pushed 2026-08 (active) (**VERIFIED** via GitHub API metadata)
  - https://github.com/KoenZomers/LidlApi — .NET, **archived** (2022) (**VERIFIED**)
  These use the Lidl Plus app API and require a Lidl Plus account login; the frequently
  cited `webapi.lidl.com` host does **not resolve** (**VERIFIED** — DNS failure), so older
  write-ups citing it are dead.
- **robots.txt:** https://www.lidl.se/robots.txt disallows `/q/search?id=*` and numeric
  prefixes; `/c/...` campaign pages are not disallowed (**VERIFIED**).

## 5. Established Swedish grocery aggregators?

- **No maintained open-source aggregator of Swedish grocery offers was found.**
  - `Mainforward/matdeal` ("Top offers and minimal price in grocery stores in Sweden",
    MIT, pushed 2026-09-17) looked promising but is a **stub**: README is one line, backend
    `main.py` is 132 bytes (**VERIFIED** via GitHub tree API). Dead lead.
  - GitHub searches for "willys api sweden", "ica scraper erbjudanden", "grocery sweden
    offers" returned only the stale/stub repos above (**VERIFIED**).
  - Commercial sites (matpriser.se-type price-comparison services) exist but no open API
    was found; **UNVERIFIED** — not investigated beyond repo search.

## Recommendation — feasibility ranking

1. **ICA — wire today.** The public erbjudanden page ships the complete weekly-offers
   dataset (with EANs and parsed mechanics) server-side; no key, no JS rendering needed.
   A ~100-line fetcher + JSON-sanitizer replaces the fictional `feeds.ica.se/week`.
2. **Lidl — wire today, add as a store.** Campaign pages under
   `https://www.lidl.se/c/erbjudanden` embed full product JSON with prices, discounts and
   validity end-dates. Path: fetch the offers index → follow campaign links → unescape and
   parse the embedded JSON. Lidl Plus API clients exist if per-member coupons are ever
   needed, but they require account credentials — not needed for the public offers.
3. **Coop — wireable, one devtools session away.** A real APIM-gated Hybris API exists and
   the subscription keys are published in the page source; only the exact resource paths
   under `external.api.coop.se` need to be captured from handla.coop.se network traffic
   before the fetcher can be written.
4. **Willys — hardest.** Real SAP OCC backend exists but is not reachable via simple URL
   probing; needs a devtools capture of the SPA's XHR calls, and robots.txt constrains
   crawling (10 s delay, 04:00–08:45 UTC window). Feasible but the most fragile.

Common design note: all four paths are "fetch page/endpoint → parse embedded JSON →
normalize to (name, brand, price, unit, validFrom/validTo, EAN)". The matapp fetcher
contract should be per-grocer adapters over that normalized shape, not a shared fictional
`{base}/veckans-extrapris` endpoint.
