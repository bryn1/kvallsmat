# T10a — Postnummer → nearest stores per chain, and store-scoped offers (MC 1355.12, parent 1355)

Researched 2026-09-26. All VERIFIED claims were confirmed by direct HTTP fetch this session
(raw responses saved under `/tmp/` during the run: `ica_butiker.html`, `willys_stores.json`,
`tjek_willys_stores.json`, `tjek_coop_stores.json`, `coop_stores.json`, `coop_detail.json`,
`coop_dr.html`). Test postnummer: **414 51 Göteborg (Majorna)**, lat 57.6914 / lon 11.9134
(geocoded via Nominatim, VERIFIED below).

**Bottom line: all four chains have a working postnummer→stores path, verified live this
session. ICA needs a geocode step (its API takes lat/lon, not postnummer); Willys and Coop
have full store lists with coordinates; Lidl has a native nearby-search. Store-scoped
offers: ICA per-store erbjudanden page (weeklyOffers with populated `stores`), Willys via
Tjek catalogs matched by store-name label, Coop via per-store dr.coop.se leaflet (PDF) +
unverified structured dke path, Lidl national (no scoping needed).**

---

## 0. Geocoding the postnummer (shared step)

- **VERIFIED — Nominatim resolves a Swedish postnummer to lat/lon without auth.**
  `GET https://nominatim.openstreetmap.org/search?postalcode=41451&country=Sweden&format=json&limit=1`
  returned:
  > `{"place_id":380747264, ... "lat":"57.6914217","lon":"11.9133518", ... "addresstype":"postcode","name":"414 51","display_name":"414 51, Kungsladugård, Centrum, Göteborg, Göteborgs Stad, Västra Götalands län, Sve..."}`
  Note the usage policy (max 1 req/s, a descriptive User-Agent is required — sent
  `matapp-research/1.0`). For production, cache geocodes per postnummer; a postnummer is a
  stable input.

## 1. ICA

### 1a. Store locator — VERIFIED

The butikssökning app (`https://www.ica.se/butiker/`) is a Vue app whose JS bundle
(`mdsa-store-vue3/assets/src-BX8MsYy3.js`, fetched live) declares its endpoints:

> `va={STORE_SEARCH:`/storesearch/v1`,CUSTOMER_STORES:`/customerstores/v1`,...ACCESS_TOKEN:`/e11/public-access-token`...}`
> `ya=e=>$().endpoints.WSO2_EXTERNAL+va[e]` with `WSO2_EXTERNAL:"https://apim-pub.gw.ica.se/sverige/digx"`
> `getStoresByPosition(e,t,n=5,r=0,i=15e3){...o=`${ya(`STORE_SEARCH`)}/searchbyquery?query=*&lon=${e}&lat=${t}&take=${n}&offset=${r}&maxdistance=${i}`...}`

Auth: an anonymous public access token, no account needed:

- `GET https://www.ica.se/e11/public-access-token` →
  > `{"publicAccessToken":"_0XBPWQQ_c4effe80-...","tokenExpires":"2026-09-26T13:04:08Z","isAnonymous":true}`

The search itself (executed live with the token above, Göteborg coordinates):

- `GET https://apim-pub.gw.ica.se/sverige/digx/storesearch/v1/searchbyquery?query=*&lon=11.9746&lat=57.7089&take=3&offset=0&maxdistance=15000`
  header `Authorization: Bearer <publicAccessToken>` → HTTP 200:
  > `{"documents":[{"id":1726,"name":"ICA Nära Heden","marketingName":"ICA Nära Heden","url":"https://www.ica.se/butiker/nara/goteborg/ica-nara-heden-1003913/","visitingAddress":"Sten Sturegatan 16","visitingZipCode":"41139","visitingCity":"Göteborg","latitude":"57.70201","longitude":"11.98227","openingHours":{...},"accountNumber":"1003913",...}`

Response fields per store: `id` (numeric store id), `name`, `marketingName`, `url`,
`visitingAddress`, `visitingZipCode`, `visitingCity`, `latitude`/`longitude` (strings),
`openingHours` (incl. `today`/`tomorrow`), `accountNumber` (the 6-digit butik number used
in URLs), `services`, `hasHomeDelivery`/`hasPickup`. `maxdistance` is in **meters**
(15000 = 15 km).

- **VERIFIED — text search works on place name** (`query=Majorna` →
  `ICA Supermarket Majorna`, Karl Johansgatan 21, 414 59 Göteborg).
- **VERIFIED (negative) — the postnummer itself is NOT a valid `query` value:**
  `query=41451` returned `{"documents":[],"stats":{"totalHits":0,...}}`. So the flow is:
  **geocode postnummer → lat/lon (Nominatim) → searchbyquery with lon/lat**. The ICA app
  itself geocodes client-side via a Google Maps key (`MAP_API_KEY` in `__INITIAL_DATA__`),
  which is browser-locked; Nominatim is the clean server-side substitute.
- **VERIFIED — the token endpoint and search both work without cookies or keys**; the
  token is anonymous and short-lived (hours), so fetch it per resolution run.

### 1b. Store-scoped offers — VERIFIED

Each store has a per-store erbjudanden page whose server-rendered HTML embeds the full
store-scoped `weeklyOffers` JSON. Fetched live:
`https://www.ica.se/erbjudanden/ica-nara-heden-1003913/` (404 KB):

> `"weeklyOffersStatus":2,"weeklyOffers":[{"id":"5004009053","details":{"brand":"Findus",...,"name":"Fryst torskryggfilé","mechanicInfo":"119 kr/st"},...,"validTo":"2026-09-27T00:00:00",...`

and the per-item `stores` field (the field T7b observed as `undefined` without a store
chosen) is **populated** on the store page:

> `"stores":[{"storeMarketingName":"ICA Nära Heden","BMSStoreId":1726,"regularPrice":"163,34","ecomDisclaimer":"","onlineInd":false,"storeInd":true,"referencePriceText":"Ord.pris 163:34 kr. 30dgr.pris 163:34 kr."...`

So: **the store-scoped ICA offer set is obtainable by fetching
`https://www.ica.se/erbjudanden/<store-slug>-<accountNumber>/` and parsing the embedded
`weeklyOffers`** — same shape as the chain-level payload matapp already ingests, with
`stores[].BMSStoreId` = the store id from the locator (`id`/`accountNumber`). The store
slug is in the locator response's `url` field (`.../erbjudanden/ica-nara-heden-1003913/`).

## 2. Willys (Axfood)

### 2a. Store locator — VERIFIED (two independent sources)

**Primary: Willys' own store list.** `GET https://www.willys.se/axfood/rest/v2/store`
(no auth, `Accept: application/json`) → HTTP 200, **258 stores**. Per store:
`storeId`, `name`, `address` (`line1`, `postalCode`, `town`, `formattedAddress`),
`geoPoint {latitude, longitude}`, `openingHours`, `clickAndCollect`, `onlineStore`,
`flyerURL`. Live sample:

> `{"name":"Willys Borås Knalleland", "address":{"line1":"Ålgårdsgatan 5-9",...,"postalCode":"506 30","town":"Borås",...}, "geoPoint":{"latitude":57.7339,"longitude":12.9331}, "storeId":2103, "flyerURL":"https://reklamblad.willys.se/willys/2103"}`

(First list element is an online/dummy store with `geoPoint 0.0/0.0` and
`"onlineStore":false`-style markers — filter on non-zero coordinates / `onlineStore`.)

Resolution: geocode postnummer → haversine over the 258 stores → nearest. No native
postal-code search endpoint was found (`/axfood/rest/v2/search/store?query=41451` → 404;
`/axfood/rest/v2/storelocator` → HTML 404 page) — the site's own butik-sök is a
CMS/JS-driven map. The full-list + haversine approach is simple and needs no extra API.

**Secondary: Tjek's store list** `GET https://squid-api.tjek.com/v2/stores?dealer_id=c371GA`
(no auth) → HTTP 200, **24 stores** with `id`, `name`, `street`, `city`, `zip_code`,
`latitude`, `longitude`:

> `{"id":"kfhat0Ym","ern":"ern:store:kfhat0Ym",...,"street":"Ulvsundavägen 189e","city":"Bromma","zip_code":"168 67","name":"Willys Stockholm Bromma","latitude":59.357,"longitude":17.9498,...}`

**CAUTION (VERIFIED): the Tjek store list is NOT the physical store universe** — 24 Tjek
stores vs 258 real Willys stores, and "Willys Borås Knalleland" (which has a Tjek
catalog) is absent from the Tjek store list. Use the Willys list for the locator; use
Tjek only for offers (below).

### 2b. Store-scoped offers — VERIFIED with one caveat

T7b/T8 established the Tjek squid API: `GET https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA`
(re-fetched live this session, HTTP 200, 24 catalogs). Each catalog is **labeled per
store**:

> `{"id":"qTZVOvPQ","label":"Willys Borås Knalleland","run_from":"2026-09-20T22:00:00+0000","run_till":"2026-09-27T21:59:59+0000",...,"offer_count":111,"dealer_id":"c371GA",...}`

- **VERIFIED (negative/caveat): the catalog↔store link is by LABEL, not by id.** In the
  catalogs list response `store_id` is `null` (checked a single catalog fetch too:
  `{"id":"qTZVOvPQ","label":"Willys Borås Knalleland","store_id":null,"store_url":null,"all_stores":false}`),
  and the Tjek store ids (`kfhat0Ym`...) do not appear in the catalog list. Matching a
  chosen physical store to its catalog must be done on the store NAME string
  (`"Willys " + store.name`), which is exact for the observed data but is a string join —
  a data-quality risk to note. Catalogs also only cover a subset of stores (24 live
  catalogs vs 258 stores); stores without a catalog fall back to chain-level/no offers.
- The per-store leaflet URL is confirmed by Willys itself: `flyerURL:
  "https://reklamblad.willys.se/willys/2103"` in the store list, and
  `GET https://www.willys.se/axfood/rest/v2/storeflyer/2103` → HTTP 200:
  > `{"displayNextWeekButton":true,...,"currentWeekUrl":"https://reklamblad.willys.se/willys/2103",...,"name":"Willys Borås Knalleland"}`

## 3. Coop

### 3a. Store locator — VERIFIED

The butikssökning app (`https://www.coop.se/butiker-erbjudanden/`, fetched live) embeds
its service config in `window.coopSettings`:

> `"storeApiUrl":"https://proxy.api.coop.se/external/store/","storeApiSubscriptionKey":"990520e65cc44eef89e9e9045b57f4e9"`

Auth: the subscription key as header `Ocp-Apim-Subscription-Key` (the key is public — it
ships in the page HTML to every visitor; same pattern T2 §3 verified for the APIM
gateway).

- `GET https://proxy.api.coop.se/external/store/stores?api-version=v1` → HTTP 200,
  **787 stores**. Basic shape:
  > `{"storeId":598,"ledgerAccountNumber":"196183","name":"Coop Krylbo","conceptId":3,"conceptName":"Coop","url":"/butiker-erbjudanden/coop/coop-krylbo/"}`
- `GET https://proxy.api.coop.se/external/store/stores/196183?api-version=v1` (by
  `ledgerAccountNumber`, must be a 6-digit string — passing the numeric storeId 598
  returns a 400 validation error, VERIFIED) → HTTP 200 with **latitude/longitude**:
  > `{"id":598,"ledgerAccountNumber":"196183","name":"Coop Krylbo","concept":{"id":3,"name":"Coop"},"address":"Järnvägsgatan 16, 77571 Krylbo","phone":"010-7412170","weeklyOffersLink":"https://dr.coop.se/butik/196183",...,"latitude":60.1307271,"longitude":16.213442,...}`

Resolution: fetch the 787-store list (basic), fetch details (lat/lon) for candidates —
or fetch all details once and cache (787 requests is heavy; the list is stable enough to
cache daily). Then geocode postnummer → haversine. The `postCode` query param on
`/coopstore` seen in the JS bundle (`/coopstore?fields=Basic&postCode=...`) 404s on both
candidate bases (VERIFIED negative: tried
`proxy.api.coop.se/external/store/coopstore?...postCode=41451` and
`external.api.coop.se/ecommerce/coop/coopstore?...` — both 404), so the
list+haversine path is the working one.

### 3b. Store-scoped offers — PARTIALLY VERIFIED

- **VERIFIED — each store has a store-scoped leaflet as PDF.** The store detail carries
  `"weeklyOffersLink":"https://dr.coop.se/butik/196183"`; fetched live, it serves a PDF
  whose metadata reads:
  > `/Title(Aktuella erbjudanden Coop Krylbo)` — i.e. the leaflet content is per store.
  This is a document, not structured JSON — usable as evidence/fallback, not as an offer
  feed.
- **UNVERIFIED — the structured per-store offers path.** The page config also embeds
  `"dkeUrl":"https://external.api.coop.se/dke/offers/","dkeKey":"32895bd5b86e4a5ab6e94fb0bc8ae234"`,
  and T7b established the offers service is consumed per chosen store client-side. Probe
  attempts this session (`/dke/offers/?store=598`, `/dke/offers/598`,
  `/dke/offers/v1?storeId=598`, `/dke/offers/v2?storeId=598` with the dkeKey as
  `Ocp-Apim-Subscription-Key`) all returned 404 — the resource path under `/dke/offers/`
  remains unknown (needs a devtools capture of coop.se with a store selected, same
  method as T2 §3). The JS bundle (`coopse.script.storesApp.c31eb03e.js`) shows a
  `POST /search/stores` store-search and `GET /stores?storeIds=` on the store API, but no
  dke resource path.
- Tjek also carries Coop: `GET https://squid-api.tjek.com/v2/stores?dealer_id=6c28SD` →
  HTTP 200, 24 stores (`{"id":"3bc5eeu",...,"name":"Stora Coop Falun","latitude":60.6029806,...}`)
  — same label-matching caveat as Willys applies to `catalogs?dealer_id=6c28SD`.

## 4. Lidl Sweden

### 4a. Store locator — VERIFIED

Lidl's store-search frontend (`/s/storesearch-frontend/26_19_4/entry/index.js`, fetched
live from lidl.se) calls the Schwarz stores API:

> `Vw=(e,t)=>{...`https://`+n+`.api.schwarz/odj/stores-api/v2/myapi/stores-frontend/`+e}` with `Qv={DEV:`dev`,TEST:`test`,QA:`qas`,PROD:`live`}`
> `tT=async()=>{let e=new Headers;...e.set(`x-apikey`,`16QaHsGX3Uc3JLhNlS2ZG1CmosbzVPs2`)...}`
> `d=e+`?limit=`+t+`&offset=`+n+`&country_code=`+r,a!==null&&o!==null&&s!==null?d+=`&nearby=`+a+`,`+o+`:`+s...&expand=${i.join(`,`)}``

Executed live:

- `GET https://live.api.schwarz/odj/stores-api/v2/myapi/stores-frontend/stores?limit=3&offset=0&country_code=SE&nearby=57.7089,11.9746:15&expand=NEARBY_STORES,GENERAL_HOURS`
  header `x-apikey: 16QaHsGX3Uc3JLhNlS2ZG1CmosbzVPs2` → HTTP 200:
  > `{"meta":{...,"total":15},"items":[{"objectNumber":"SE00346","objectType":"STORE","storeName":"Gbg Nordstan","distance":0.2,"address":{"streetName":"Postgatan","streetNumber":"26","city":"Göteborg","zip":"411 06",...,"longitude":11.97095,"latitude":57.70874},"status":{"name":"open",...},"openingHours":{...},"generalOpeningHours":{...},"marketingData":{"externalUrl":null,"offerRegion":2,"offerRegionName":"Halmstad 2","zone":"SE1","zoneName":"SE National",...}}]}`

Notes: `nearby=lat,lon:radiusKm` with radius 1–100 (the API rejects 15000 with a regex
error — VERIFIED: `"parameter \"nearby\" ... doesn't match the regular expression
\"^(-?\\d+(\\.\\d+)?),\\s*(-?\\d+(\\.\\d+)?):([1-9][0-9]?|100)$\""`); results carry a
server-computed `distance` (km); `objectNumber` is the store id; `offerRegion`/
`offerRegionName` tie into the campaign payload's region dimension (T7b §4). The
`x-apikey` is a static public key shipped in the site JS — no auth flow.

### 4b. Store-scoped offers — not needed

Lidl is national (T7b §4: one `regionPriceId` across all seven DC regions). The locator
response's `offerRegion`/`offerRegionName` confirms the region dimension exists but is
uniform in practice. No store scoping required; existing national ingestion stands.

## 5. Integration recommendation for matapp (minimal)

Extends, does not replace: the existing `profile.selected_stores` (chain ids) and the
offers table with nullable `store_id` recommended in T7b. What it replaces: nothing —
chain-level ingestion stays the fallback when no store is resolved.

1. **Profile gains `postal_code` (nullable string) and `resolved_stores` (nullable
   JSON list of `{chain, store_id, store_name, lat, lon, distance_km}`).** A resolver
   service (one module, e.g. `src/stores/locator.py`) implements per chain:
   - geocode postnummer once via Nominatim (cache by postnummer);
   - ICA: public-access-token → `storesearch/v1/searchbyquery?query=*&lon&lat&take&maxdistance=15000`;
   - Willys: `axfood/rest/v2/store` list (cache daily) + haversine;
   - Coop: `proxy.api.coop.se/external/store/stores` + per-store detail for lat/lon (cache daily);
   - Lidl: `live.api.schwarz/.../stores?...&nearby=lat,lon:15` (native nearest).
   Resolution runs on profile save (POST profile with postal_code → resolved_stores
   returned and stored); the user can override per chain.
2. **Offers gain `store_id` (nullable)** as T7b recommended. Population per chain:
   - ICA: ingest the per-store erbjudanden page for each resolved ICA store (same
     weeklyOffers parser, `stores[].BMSStoreId` = store_id);
   - Willys: match resolved store name → Tjek catalog label; ingest that catalog's
     hotspots with store_id set (existing Tjek adapter, one extra param);
   - Coop: BLOCKED on the dke resource path (devtools capture needed) — until then Coop
     offers stay chain-level with `store_id` NULL;
   - Lidl: stays chain-level, `store_id` NULL by design.
3. **Menu filtering**: when the profile has resolved stores, `/api/menu` filters offers
   to `store_id IN (resolved stores for the offer's chain) OR store_id IS NULL` — NULL
   means "chain-level, valid everywhere" (Lidl, and Coop until unblocked). This is a
   one-line extension of the existing store filter (T4b), not a new mechanism.

Risk notes: Tjek catalog↔store matching is a string join (Willys) — log unmatched
stores rather than silently dropping; ICA token is short-lived — fetch per run; Coop
787-detail fetches should be cached, not per-request.

---

Evidence files this session (raw fetches): `/tmp/ica_butiker.html`,
`/tmp/ica_index.js`, `/tmp/src-BX8MsYy3.js`, `/tmp/ica_store_offers.html`,
`/tmp/willys_stores.json`, `/tmp/willys_stores.json` (258 stores),
`/tmp/tjek_willys.json`, `/tmp/tjek_willys_stores.json`, `/tmp/tjek_coop_stores.json`,
`/tmp/coop_stores.json`, `/tmp/coop_detail.json`, `/tmp/coop_dr.html` (PDF),
`/tmp/lidl_index.js`, plus live curl transcripts quoted above.

# VERDICT: PASS
