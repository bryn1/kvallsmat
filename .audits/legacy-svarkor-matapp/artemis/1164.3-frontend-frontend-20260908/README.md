# Phase 8 (T7) frontend — matapp framtidsvision

Kort **1164.3** (artemis, `[type:frontend]`, seat-pin nicked borttagen 2026-09-02).
Förbereds av Phase 7 (api-lager, 1164.1) som är klart och `completed_unverified`.

## Vad detta är

De tre vyerna i MVP-visionen, byggda prefix-medvetna enligt Phase 8 DoD:

| Vy | Modul | Backend (Phase 7/5/3) |
|----|-------|------------------------|
| **auth /** Konto | `static/js/ui/auth.js` | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| **profil** | `static/js/ui/profile.js` | `GET|PUT /api/profile` (auth-skyddad) |
| **3 förslag** | `static/js/ui/suggestions.js` | `GET /api/menu` (auth-/profil-skyddad) → 3 suggestions |

Alla anrop går genom **`utils/api.js`** som är **prefix-medveten** (ärver POC 1111.1-fixen
`resolveApiBase` — aldrig hårdkodad `/matapp`). Moduler läses i ordningen
utils → ui → app.js och körs via globala `window.*`-alias (POC-idiom).

Bootstrap: `app.js` kopplar nav-flikarna och visar **Konto**-vyn först; när en vy görs
synlig refreshar den sin data.

## Leveransstruktur

```
1164.3-frontend-frontend-20260908/
  templates/index.html               — singel sida, tre <section> vyer (Konto/Profil/3 förslag)
  static/js/utils/api.js             — prefix-medveten API-klient (transport + Endpoints)
  static/js/ui/auth.js               — login/logout/me
  static/js/ui/profile.js            — profil GET|PUT
  static/js/ui/suggestions.js        — /api/menu → 3 cards
  static/js/app.js                   — bootstrap, view-switching
  static/css/app.css                 — minimal design (design tokens)
  harness_gate_c7.js                 — frontend-harness (C7-DoD-körbar)
  README.md
```

## Harness — kör den

`harness_gate_c7.js` läser denna träds index.html + skripten in i jsdom, mockar
`window.fetch`, sätter sidan vid `/matapp/` (det verkliga prefixet som nginx strippar),
och bevisar gate-C7-DoD:
1. **headless render (non-blank)** av auth/profil/3-förslag, exit 0
2. **API-anrop mot `/matapp/`-prefixet INTE `/`** — den fångar varje fetch och kräver
   `/matapp/` (`assertPrefixed`), rött om en anrop saknar prefix
3. **en vy som inte prefixar → RÖD**: litmus-körning laddar en trasig `api.js`-variant
   (`API_BASE=''` — prefixet tappat) och visar att gaten fångar `/api/...`-anropen.
   Gaten KAN gå rött (inte false-green).

Använder jsdom från Hermes-installationen (`/usr/local/lib/hermes-agent/node_modules/jsdom`).

```
node harness_gate_c7.js .    # . = root; eller ange absolut frontend-root
# exit 0 = ALL-CHECKS-PASS (grönt + rött case); non-zero = failure.
```

## Notera (beslut)
- **Tyvärr ingen riktig view med riktig data mot live-beckend här** — jsdom har ingen riktig
  `fetch` till nätverket. Harnesset mockar backend-svaren för att bevisa att vyerna
  renderar non-blank och prefixar sina anrop. Riktig end-to-end mot live-url sker i
  Phase 9/10 (hosting → henrik, post-publish-accept).
- Dep från POC bevarade: relativa `static/...`-refs + `?v=` cache-buster, prefix-medveten
  api.js (LEGEND från briefen) — det är en läxa att bevara, inte skriva om.
- **Språk–val:** frontend är JavaScript (fortsätter POC-stacken; inget att portas till Rust —
  glue/UI, repo-idiom är JS).

## Verifierad
Kommandon och utdata i `1164.3-frontend-evidence-20260908.md` (denna katalog är leveransen).
`VERIFY_EXIT=0` från `node harness_gate_c7.js .`.
