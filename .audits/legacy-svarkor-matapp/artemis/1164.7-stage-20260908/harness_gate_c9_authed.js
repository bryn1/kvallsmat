// harness_gate_c9_authed.js — T9 (MC 1164.7) AUTHENTICATED end-to-end flow.
//
// WHY this exists next to the /usr/local/bin/postpublish-accept.sh DoD bar:
// the bar is cookie-less — it proves the UNAUTHENTICATED surface (reachable,
// renders pixels+vision, tab clicks, console, assets). It cannot prove the
// authed golden path (login -> profile roundtrip -> /api/menu 3 suggestions ->
// logout), which is the "varje funktion" half of the Phase 10 bar on an app
// whose data endpoints are auth-protected BY DESIGN (gates C2/C4/C6 mandate 401
// when there is no session). This harness drives a REAL browser (agent-browser,
// the same binary the bar uses) through that path.
//
//   RED litmus (calibration, runs FIRST): a WRONG password must surface the
//     app's #auth-error banner — the flow provably can fail (no false-green).
//   GREEN: real login -> greeting names the user; suggestions view renders
//     exactly 3 cards via the session cookie; profile save+read-back roundtrip
//     through the real form; ZERO console/page errors across the walk; logout
//     clears the session and the login form returns.
//
// USAGE: node harness_gate_c9_authed.js [url] [credfile]
//   url default http://127.0.0.1:8398/ (staged local serve; pass the live URL
//   once published). credfile default ./acceptance-user.json (written by
//   run_local.py). Credentials are READ from the file — never hardcoded, never
//   echoed; the wrong-password litmus value is random junk.
// exit 0 = green + litmus held; 1 = a check went red; 2 = cannot perform.
"use strict";
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

let AB = path.join(os.homedir(), ".hermes/hermes-agent/node_modules/agent-browser/bin/agent-browser.js");
if (!fs.existsSync(AB)) AB = "/usr/local/lib/hermes-agent/node_modules/agent-browser/bin/agent-browser.js";
if (!fs.existsSync(AB)) { console.error("CANNOT-PERFORM: agent-browser not found"); process.exit(2); }

const URL = process.argv[2] || "http://127.0.0.1:8398/";
const CRED = process.argv[3] || path.join(__dirname, "acceptance-user.json");
if (!fs.existsSync(CRED)) { console.error("CANNOT-PERFORM: credfile missing: " + CRED); process.exit(2); }
const creds = JSON.parse(fs.readFileSync(CRED, "utf8"));
const USER = creds.username, PASS = creds.password;
if (!USER || !PASS) { console.error("CANNOT-PERFORM: credfile malformed"); process.exit(2); }

function ab() {
  const args = Array.prototype.slice.call(arguments);
  return execFileSync("node", [AB].concat(args), {
    encoding: "utf8", timeout: 120000, stdio: ["ignore", "pipe", "pipe"],
  });
}

let failures = 0;
function check(name, cond, detail) {
  if (cond) { console.log("[ok]   " + name); }
  else { console.log("[FAIL] " + name + (detail ? " :: " + String(detail).trim() : "")); failures++; }
}
const isVisible = (sel) => /true/i.test(ab("is", "visible", sel));

(async () => {
  try { ab("close", "--all"); } catch (e) { /* fresh session */ }
  // --no-sandbox: required on vm104/vm105 (apparmor_restrict_unprivileged_userns=1),
  // same flag the DoD bar itself passes (postpublish-accept.sh line 238).
  ab("open", URL, "--args", "--no-sandbox");
  ab("wait", "2000");

  // ---- 1. RED litmus FIRST: wrong password -> #auth-error (two-sided gate) ----
  ab("click", "a[data-page=\"auth\"]");
  ab("fill", "#auth-input-user", USER);
  ab("fill", "#auth-input-pass", "wrong-" + Date.now() + "-" + Math.random());
  ab("click", "#auth-submit");
  ab("wait", "1500");
  check("RED litmus: wrong password surfaces #auth-error", isVisible("#auth-error"),
    "UI accepted a wrong password — auth not enforced client-side");

  // ---- 2. GREEN: real login -> status greeting names the user ----
  ab("fill", "#auth-input-user", USER);
  ab("fill", "#auth-input-pass", PASS);
  ab("click", "#auth-submit");
  ab("wait", "1500");
  check("login: #auth-status visible", isVisible("#auth-status"));
  const greeting = ab("get", "text", "#auth-username").trim();
  check("login: greeting names the user", greeting.indexOf(USER) >= 0, "got '" + greeting + "'");

  // ---- 3. /api/menu with the session cookie -> exactly 3 suggestion cards ----
  ab("click", "a[data-page=\"suggestions\"]");
  ab("wait", "3000");
  const cardCount = parseInt(ab("get", "count", ".suggestion-card").trim(), 10);
  check("menu: 3 suggestion cards rendered", cardCount === 3, "count=" + cardCount);
  check("menu: error banner NOT visible", !isVisible("#suggestions-error"));

  // ---- 4. profile save -> read-back roundtrip through the real form ----
  ab("click", "a[data-page=\"profile\"]");
  ab("wait", "2000");
  ab("fill", "#profile-persons", "5");
  ab("fill", "#profile-meal-days", "4");
  ab("fill", "#profile-budget", "1234");
  ab("click", "#profile-form button[type=\"submit\"]");
  ab("wait", "2000");
  const saved = ab("get", "text", "#profile-status");
  check("profile: save reports Sparat", /sparat/i.test(saved), "status='" + saved.trim() + "'");
  ab("click", "a[data-page=\"auth\"]"); ab("wait", "400");
  ab("click", "a[data-page=\"profile\"]"); ab("wait", "2500");
  const persons = ab("get", "value", "#profile-persons").trim();
  const budget = ab("get", "value", "#profile-budget").trim();
  check("profile: persons roundtrips (5)", persons === "5", "got '" + persons + "'");
  check("profile: kron-budget roundtrips (1234)", budget === "1234", "got '" + budget + "'");

  // ---- 5. zero console/page errors across the whole authed walk ----
  const consoleLog = ab("console", "--filter", "error");
  const pageErrs = ab("errors");
  const cErr = consoleLog.split("\n").filter((l) => l.trim()).join(" | ");
  const pErr = pageErrs.split("\n").filter((l) => l.trim()).join(" | ");
  check("authed walk: 0 console errors", cErr === "", cErr);
  check("authed walk: 0 page errors", pErr === "", pErr);

  // ---- 6. logout clears the session -> login form returns ----
  ab("click", "a[data-page=\"auth\"]");
  ab("wait", "400");
  ab("click", "#auth-logout");
  ab("wait", "1500");
  check("logout: login form visible again (session cleared)", isVisible("#auth-form"));

  console.log(failures === 0 ? "AUTHED_RESULT=PASS" : "AUTHED_RESULT=FAIL (" + failures + ")");
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => { console.error("harness error:", e.message); process.exit(2); });
