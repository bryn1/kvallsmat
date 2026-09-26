# [type:frontend] audit: vision click-through — varje klick, varje länk (matapp)

Du är GATE. Adversarial vision-audit av LIVE-sajten https://sibbamala.com/matapp/
(POC-tillståndet, revert 12e2e30). Använd browser_navigate + browser_console + browser_snapshot
+ browser_vision.

## Uppgift
1. Navigera till https://sibbamala.com/matapp/ — console FÖRST: 404-asset eller JS-exception = FAIL.
2. Klicka IGENOM varje interaktivt element (butiksväljare, meny-generering, alla knappar, länkar,
   formulär). För varje klick: vad händer? console-fel? tomt svar? trasig render?
3. Testa alla länkar på sidan (href-targets) — döda länkar = fynd.
4. browser_vision på minst 3 tillstånd (startvy, meny genererad, butiker valda):
   - kontrast/läsbarhet, överlapp, avklippt text
   - konsistent palett/typografi
   - mobil-bredd (narrow viewport är SPEC — owner testar på telefon)
5. Kolla /matapp/api/menu med och utan query-params (422 utan params — är felmeddelandet begripligt
   i UI:t eller ser användaren bara "error"?).

## DoD / Acceptance
DoD: Klick-logg med varje interaktivt element → resultat (OK/fel + console-utdrag); länklista med HTTP-koder; vision-fynd per vy inkl. narrow-viewport; varje påstående märkt VERIFIED eller BLOCKED; rapport sparad som /srv/workspace/svarkor-matapp/audit/vision-clickthrough.md med evidence + VERIFY_EXIT=0.
