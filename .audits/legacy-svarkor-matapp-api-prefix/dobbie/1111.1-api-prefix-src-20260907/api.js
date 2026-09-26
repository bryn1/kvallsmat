// ============================================================================
// utils/api.js — Shared API client for Kvällsmat
// ============================================================================
// Centralises the API base URL and endpoint paths so feature modules (stores.js,
// menu.js) don't hardcode URLs. Loaded before all ui modules as a plain
// <script> (no ES modules) so its bindings are shared global scope.
//
// Depends on nothing. Render-only callers never compute business state here —
// this is purely transport helpers.
// ============================================================================

// Prefix-aware API base (MC 1111.1): the renderer's nginx serves the app under
// /matapp/ and STRIPS that prefix before proxying to the backend, so the
// browser must request /matapp/api/... while the backend still sees /api/....
// Derive the base from the page path so it also works mounted at root ("") and
// is robust to the app moving to another prefix -- no hardcoded "/matapp".
function resolveApiBase(pathname) {
  const seg = (pathname || '').split('/')[1];
  return seg ? '/' + seg : '';
}
const API_BASE = resolveApiBase(window.location.pathname);

/**
 * Perform a GET request against the API.
 * @param {string} path - API path (from `Endpoints`)
 * @returns {Promise<Response>} The fetch Response (callers keep res.json())
 * @throws {Error} On 4xx/5xx HTTP status
 */
async function apiGet(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

/**
 * Perform a JSON POST request against the API.
 * @param {string} path - API path (from `Endpoints`)
 * @param {Object} body - JSON body
 * @returns {Promise<Response>} The fetch Response
 * @throws {Error} On 4xx/5xx HTTP status
 */
async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

// Central registry of API endpoints.
const Endpoints = {
  stores: '/api/stores',
  storeSelect: '/api/stores/select',
  storeSelected: '/api/stores/selected',
  menu: '/api/menu',
};
