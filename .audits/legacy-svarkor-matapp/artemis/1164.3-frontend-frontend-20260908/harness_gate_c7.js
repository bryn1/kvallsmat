#!/usr/bin/env node
// ============================================================================
// harness_gate_c7.js — Phase 8 (T7) frontend gate C7 harness
// (card 1164.3, artemis)
// ============================================================================
// DoD (gate C7, gate-p8.txt / PHASE0.md §P Phase 8):
//   1. headless render (non-blank) of every view (auth/profil/3-förslag) exit 0
//   2. API-anrop mot /matapp/-prefixet INTE /
//   3. en vy som inte prefixar anrop -> RÖD (harness self-test / go red)
//
// This harness loads the REAL frontend source (templates/index.html + each
// script) into jsdom with a mocked window.fetch, sets the page at /matapp/
// (the real hosting prefix), verifies each view renders non-blank, verifies the
// captured fetch URLs start with /matapp/ (never a bare /), and runs a litmus
// RED case where a broken api.js variant DROPS the prefix — that unprefixed
// call must be flagged so the gate provably CAN go red (not false-green).
//
// USAGE: node harness_gate_c7.js <frontend-root>
//   where <frontend-root> defaults to the dir this script sits in.
//   exit 0 = both green + red cases pass; non-zero = failure.
// ============================================================================

const fs = require('fs');
const path = require('path');

const JSDOM = require('/usr/local/lib/hermes-agent/node_modules/jsdom').JSDOM;

// ---- resolve the frontend root (dir containing templates/ + static/) ----
const root = process.argv[2] || __dirname;

function readFile(p) {
  return fs.readFileSync(path.join(root, p), 'utf8');
}

(async () => {

// Build a jsdom environment from the real index.html + real scripts,
// optionally overriding the api.js source (for the RED litmus case).
function boot(fetchFn, locationPath, apiOverride) {
  const html = readFile('templates/index.html');

  // Use a synthetic URL whose PATH is /matapp/index.html so resolveApiBase
  // sees /matapp — the real nginx prefix the renderer strips on proxy.
  const dom = new JSDOM(html, {
    url: 'https://sibbamala.com' + (locationPath || '/matapp/index.html'),
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });

  // Mock fetch BEFORE any module code runs; capture the requested URLs.
  const requested = [];
  dom.window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    requested.push(url);
    return fetchFn(url);
  };

  // The real script order (index.html script tags, utils -> ui -> app last).
  const scripts = [
    'static/js/utils/api.js',
    'static/js/ui/auth.js',
    'static/js/ui/profile.js',
    'static/js/ui/suggestions.js',
    'static/js/app.js',
  ];

  // Execute all real scripts in ONE eval so top-level const/let share the
  // same global lexical scope — exactly as a real browser treats them.
  const combined = scripts
    .map((s) => (s === 'static/js/utils/api.js' && apiOverride ? apiOverride : readFile(s)))
    .join('\n;\n');
  dom.window.eval(combined); // eslint-disable-line no-eval

  return { dom, requested };
}

// ---- canned API responses for the three endpoints ----
class Response {
  constructor(body, init) { this._body = body; this.status = init.status; }
  async json() { return JSON.parse(this._body); }
  get ok() { return this.status >= 200 && this.status < 300; }
}
function cannedFetch(url) {
  if (/\/api\/auth\/me$/.test(url)) {
    return Promise.resolve(new Response(JSON.stringify({ user_id: 1, username: 'testuser' }), { status: 200 }));
  }
  if (/\/api\/profile$/.test(url)) {
    return Promise.resolve(new Response(
      JSON.stringify({ persons: 3, meal_days: 5, kron_budget: 900, selected_stores: [] }),
      { status: 200 }));
  }
  if (/\/api\/menu$/.test(url)) {
    return Promise.resolve(new Response(JSON.stringify({
      week_key: '2026-W34',
      suggestions: [
        { week_key: '2026-W34', seed: 101, days: [
          { date: '2026-08-17', dish_id: 'pasta', andel_extrapris: 0.8 },
          { date: '2026-08-18', dish_id: 'soppa', andel_extrapris: 0.6 },
        ] },
        { week_key: '2026-W34', seed: 202, days: [
          { date: '2026-08-17', dish_id: 'sallad', andel_extrapris: 0.9 },
        ] },
        { week_key: '2026-W34', seed: 303, days: [
          { date: '2026-08-18', dish_id: 'tacos', andel_extrapris: 1.0 },
        ] },
      ],
    }), { status: 200 }));
  }
  return Promise.resolve(new Response(JSON.stringify({}), { status: 404 }));
}

let failures = 0;
function check(name, cond) {
  if (cond) { console.log(`[ok]   ${name}`); }
  else { console.log(`[FAIL] ${name}`); failures++; }
}

// Every requested API url must target the /matapp/ prefix, never a bare '/'.
function assertPrefixed(requested, label) {
  const bad = requested.filter((u) => !u.includes('/matapp/'));
  check(`${label}: every API call targets /matapp/ prefix (never bare /)`, bad.length === 0);
  if (bad.length) bad.forEach((u) => console.log(`       BAD (unprefixed): ${u}`));
}

// Render-non-blank assertion: the view's section must contain meaningful text.
function assertNonBlank(dom, viewId, label) {
  const doc = dom.window.document;
  const section = doc.getElementById(viewId);
  check(`${label}: view #${viewId} exists`, !!section);
  if (!section) return;
  const text = (section.textContent || '').replace(/\s+/g, ' ').trim();
  check(`${label}: view is non-blank (text length ${text.length})`, text.length > 4);
}

// ---------------------------------------------------------------------------
// GREEN CASE — the real frontend at the /matapp/ prefix
// ---------------------------------------------------------------------------
console.log('== GREEN CASE: real frontend, page mounted at /matapp/ ==');
{
  const { dom, requested } = boot(cannedFetch, '/matapp/index.html');
  const settle = new Promise((res) => setTimeout(res, 200));
  await settle;

  const doc = dom.window.document;
  assertNonBlank(dom, 'page-auth', 'auth');
  check('auth view shows logged-in username', /testuser/.test(doc.getElementById('page-auth').textContent));

  assertNonBlank(dom, 'page-profile', 'profile');
  // The form inputs hold the fetched values in their VALUE, not textContent.
  const budgetInput = doc.getElementById('profile-budget');
  check('profile view populated (kronbudget from placed GET)',
    budgetInput && budgetInput.value === '900');

  assertNonBlank(dom, 'page-suggestions', 'suggestions');
  check('suggestions view shows 3 suggestion cards',
    doc.querySelectorAll('.suggestion-card').length === 3);

  assertPrefixed(requested, 'GREEN');
  const uses = requested.map((u) => u.replace('https://sibbamala.com', '')).join(' | ');
  console.log(`       captured calls: ${uses}`);
}

// ---------------------------------------------------------------------------
// RED CASE — litmus: a module that DROPS the prefix must be flagged RED
// ---------------------------------------------------------------------------
console.log('== RED CASE: broken api.js (no prefix) must be flagged RED ==');
{
  // Break REAL source: api.js rewritten so resolveApiBase returns '' (no
  // prefix). Everything else is the real files. The real modules run unaltered
  // against this broken transport and SHOULD produce an unprefixed fetch.
  const brokenApi = readFile('static/js/utils/api.js')
    .replace(/const API_BASE = resolveApiBase\(window.location.pathname\);/,
      "const API_BASE = ''; // BROKEN: no prefix");

  const { dom, requested } = boot(cannedFetch, '/matapp/index.html', brokenApi);
  const settle = new Promise((res) => setTimeout(res, 200));
  await settle;

  // The gate's assertion on the ACTUALLY captured requests (not hand-injected).
  const bad = requested.filter((u) => !u.includes('/matapp/'));
  if (bad.length > 0) {
    bad.forEach((u) => console.log(`[red] unprefixed call captured: ${u}`));
    console.log('[RED-CASE-OK] the prefix check flags an unprefixed view (litmus passed)');
  } else {
    console.log('[FAIL] the prefix check did NOT flag the broken view (false-green gate)');
    failures++;
  }
}

console.log(failures === 0 ? 'ALL-CHECKS-PASS' : `FAILURES=${failures}`);
process.exit(failures === 0 ? 0 : 1);
})();
