# [type:security] audit: säkerhet (matapp)

Du är GATE. Adversarial säkerhets-audit av matapp, BÅDE live-POC:n (/srv/workspace/hosting/apps/matapp/)
och framtidsversionen (git show 4d220cd i samma klon).

## Kontext (viktigt — läs innan du rapporterar "saknad auth" som fynd)
POC:n är MED DESIGN open-login (ägaren har uttryckligen ruleat att matapp POC ska vara öppen,
alla kan använda den utan inloggning). "Ingen auth på POC" är alltså INTE ett fynd i sig.
Framtidsversionen (4d220cd) HAR auth (argon2id + session-cookie) — granska den istället.

## Uppgift
1. Injection: var når untrusted input en query, shell eller filväg? Parametriserade queries?
2. Secrets: något i koden, loggarna eller config? Referera ENDAST med sökväg, echo:a aldrig innehåll.
3. Fel-läckage: stack traces, interna sökvägar, DB-schema till användaren?
4. Session-hantering i 4d220cd: cookie-attribut (HttpOnly, Secure, SameSite), session-lagring,
   utloggning, brute-force på login?
5. demo_guard: finns den i matapp-kopian? Vad skyddar den mot?
6. Externa anrop: feed-fetcher (willys/ica/coop) — SSRF-risk, token-hantering, timeouts.
7. Filbehörigheter: STATE_DIRECTORY, sqlite-fil.

## DoD / Acceptance
DoD: Fynd-tabell med severity (CRITICAL/HIGH/MEDIUM/LOW), fil:rad för varje fynd, VERIFIED/UNVERIFIED-märkning; POC open-login explicit bedömd som by-design (ej fynd); rapport sparad som /srv/workspace/svarkor-matapp/audit/security.md med evidence + VERIFY_EXIT=0.
