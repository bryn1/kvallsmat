// ============================================================================
// ui/suggestions.js — 3-förslag view (auth-/profil-skyddad /api/menu) — render-only
// (Phase 8 T7 frontend, gate C7)
// ============================================================================
// Fetches /api/menu (the api-lager's headline endpoint, Phase 7 gate C6) with the
// session cookie and renders the THREE suggestions (families) that come back.
// Each suggestion is {week_key, seed, days[]}, each day {date, dish_id,
// andel_extrapris}. Render-only: it draws the DOM from backend data and never
// computes a menu itself (REV2 invariant #2).
//
// Prefix-aware via utils/api.js — every /api/* call resolves to /matapp/api/*
// under nginx (gate C7's "API-anrop mot /matapp/-prefixet").
// ============================================================================

const suggestionsModule = (() => {
  // ---- Data accessor (render-only) ----
  async function fetchSuggestions() {
    const res = await apiGet(Endpoints.menu);
    return await res.json(); // {week_key, suggestions:[{week_key, seed, days:[...]}]}
  }

  // ---- Rendering: a single suggestion family ----
  // MC 1355.16: when the menu response carries offer_sources, append the
  // store scope to each day's line (display only; no logic).
  function renderSuggestion(sug, index, sourceNames) {
    const week = sug && sug.week_key ? sug.week_key : '';
    const seed = sug && sug.seed != null ? sug.seed : '';
    const days = Array.isArray(sug && sug.days) ? sug.days : [];
    const dishes = days.map((d) => {
      const pct = Math.round((d.andel_extrapris != null ? d.andel_extrapris : 0) * 100);
      const storeScopes = (d.used_offer_ids || [])
        .map((id) => sourceNames && sourceNames.get(id))
        .filter(Boolean);
      const storeLabel = storeScopes.length ? ` · butik: ${[...new Set(storeScopes)].join(', ')}` : '';
      return `<li class="suggestion__day">
        <span class="suggestion__dish">${d.dish_id || 'Recept saknas'}</span>
        <span class="suggestion__extra">${d.date || ''} · ${pct}% extrapris${storeLabel}</span>
      </li>`;
    }).join('');

    return `<article class="suggestion-card">
      <header class="suggestion-card__header">
        <span class="suggestion-card__index">Förslag ${index + 1}</span>
        <span class="suggestion-card__meta">seed ${seed} · vecka ${week}</span>
      </header>
      <ul class="suggestion-card__days">${dishes || '<li class="suggestion__day">Inga rätter</li>'}</ul>
    </article>`;
  }

  // ---- Rendering: all three ----
  function render(data) {
    const suggestions = (data && Array.isArray(data.suggestions)) ? data.suggestions : [];
    // offer_id -> store scope (display only; absent offer_sources = no label).
    const sourceNames = new Map(
      ((data && Array.isArray(data.offer_sources)) ? data.offer_sources : [])
        .filter((s) => s && s.store_id)
        .map((s) => [s.offer_id, s.store_id]));
    const grid = document.getElementById('suggestions-grid');
    const countEl = document.getElementById('suggestions-count');
    const emptyEl = document.getElementById('suggestions-empty');
    const errorEl = document.getElementById('suggestions-error');

    if (countEl) countEl.textContent = suggestions.length
      ? `${suggestions.length} förslag`
      : '';
    if (grid) grid.innerHTML = suggestions.map((sug, i) => renderSuggestion(sug, i, sourceNames)).join('');
    if (emptyEl) emptyEl.hidden = suggestions.length > 0;
    if (errorEl) errorEl.hidden = true;
  }

  // ---- Banner switching ----
  function setBanner(which) {
    const loading = document.getElementById('suggestions-loading');
    const error = document.getElementById('suggestions-error');
    const grid = document.getElementById('suggestions-grid');
    if (loading) loading.hidden = which !== 'loading';
    if (error) error.hidden = which !== 'error';
    if (grid) grid.hidden = (which === 'loading' || which === 'error');
  }

  // ---- Load on view enter ----
  async function load() {
    setBanner('loading');
    try {
      const data = await fetchSuggestions();
      render(data);
    } catch (err) {
      console.error('Failed to load suggestions:', err);
      setBanner('error');
    }
  }

  function bindRetry() {
    const btn = document.getElementById('suggestions-retry');
    if (btn) btn.addEventListener('click', load);
  }

  function init() {
    bindRetry();
    load();
  }

  return { init, load, render, renderSuggestion };
})();

// Global alias (POC idiom): app.js bootstraps via window-scope module.
window.suggestionsModule = suggestionsModule;
