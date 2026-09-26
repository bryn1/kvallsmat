// ============================================================================
// ui/profile.js — Profile view (auth-skyddad /api/profile GET|PUT) — render-only
// (Phase 8 T7 frontend, gate C7)
// ============================================================================
// Loads the authenticated user's profile (persons, meal_days, kron_budget,
// selected_stores) via GET /api/profile and renders an edit form; on submit PUTs
// it back. 404 (no profile yet) renders the same empty form. 401 is handled by
// the auth view (this view just reports "not logged in"). Render-only: draws
// the form from backend data, never computes household state itself.
// ============================================================================

const profileModule = (() => {
  // MC 1355.16: absent-means-unchanged PUT semantics — postal_code is only
  // included in the PUT body when the user actually edited the field.
  let postalEdited = false;

  // ---- Data accessors (render-only) ----
  async function fetchProfile() {
    const res = await apiGet(Endpoints.profile);
    return await res.json(); // {persons, meal_days, kron_budget, selected_stores, postal_code, resolved_stores}
  }

  async function saveProfile(data) {
    const res = await apiPut(Endpoints.profile, data);
    return await res.json(); // {saved, profile_id, profile:{...}}
  }

  // ---- Fill the form from a profile object ----
  function fillForm(profile) {
    const personsEl = document.getElementById('profile-persons');
    const mealDaysEl = document.getElementById('profile-meal-days');
    const budgetEl = document.getElementById('profile-budget');
    const postalEl = document.getElementById('profile-postal');
    const statusEl = document.getElementById('profile-status');

    if (personsEl) personsEl.value = profile && profile.persons != null ? profile.persons : 2;
    if (mealDaysEl) mealDaysEl.value = profile && profile.meal_days != null ? profile.meal_days : 5;
    if (budgetEl) budgetEl.value = profile && profile.kron_budget != null ? profile.kron_budget : '';
    if (postalEl) postalEl.value = (profile && profile.postal_code) || '';
    postalEdited = false;
    renderResolved(profile && profile.resolved_stores);
    if (statusEl) {
      statusEl.textContent = profile ? 'Profil laddad.' : 'Ingen profil än — fyll i och spara för att skapa en.';
      statusEl.hidden = false;
    }
  }

  // ---- Render the persisted resolved stores (per-chain status + resolved_at) ----
  function renderResolved(resolved) {
    const el = document.getElementById('profile-resolved');
    if (!el) return;
    if (!resolved || !resolved.chains) { el.hidden = true; el.innerHTML = ''; return; }
    const lines = [];
    for (const [chain, entry] of Object.entries(resolved.chains)) {
      if (entry && entry.status === 'ok') {
        for (const s of entry.stores || []) {
          lines.push(`${s.store_name} (${chain}) · ${s.distance_km} km`);
        }
      } else {
        lines.push(`${chain}: kunde inte hämtas${entry && entry.error ? ` — ${entry.error}` : ''} — spara om profilen för att försöka igen.`);
      }
    }
    if (resolved.resolved_at) {
      lines.push(`Hämtat: ${resolved.resolved_at}`);
    }
    el.innerHTML = lines.map((l) => `<p>${l}</p>`).join('');
    el.hidden = lines.length === 0;
  }

  // ---- Submit: collect + PUT ----
  async function submitProfile() {
    const persons = parseInt(document.getElementById('profile-persons')?.value, 10);
    const mealDays = parseInt(document.getElementById('profile-meal-days')?.value, 10);
    const budgetVal = document.getElementById('profile-budget')?.value;
    const kronBudget = budgetVal ? parseInt(budgetVal, 10) : 0;

    const data = {
      persons: Number.isNaN(persons) ? 2 : persons,
      meal_days: Number.isNaN(mealDays) ? 5 : mealDays,
      kron_budget: Number.isNaN(kronBudget) ? 0 : kronBudget,
      selected_stores: [],
    };
    // Absent = unchanged (backend semantics); only an edit is sent. An edit
    // to empty sends null = explicit clear.
    if (postalEdited) {
      const postalVal = document.getElementById('profile-postal')?.value?.trim() || '';
      data.postal_code = postalVal === '' ? null : postalVal;
    }
    try {
      const res = await saveProfile(data);
      fillForm(res.profile || data);
      const statusEl = document.getElementById('profile-status');
      if (statusEl) { statusEl.textContent = 'Sparat!'; statusEl.hidden = false; }
    } catch (err) {
      console.error('Profile save failed:', err);
      const statusEl = document.getElementById('profile-status');
      if (statusEl) { statusEl.textContent = 'Kunde inte spara profilen.'; statusEl.hidden = false; }
    }
  }

  // ---- Load on enter ----
  async function load() {
    let profile = null;
    try {
      profile = await fetchProfile();
    } catch (err) {
      // 404 = none saved yet; 401 handled by auth view. Render empty form either way.
      console.error('Failed to load profile (404 ok):', err);
    }
    fillForm(profile);
  }

  function bindSubmit() {
    const form = document.getElementById('profile-form');
    if (form) form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      submitProfile();
    });
    // MC 1355.16: track edits so the PUT body carries postal_code only when
    // the user changed it (absent = unchanged backend semantics).
    const postalEl = document.getElementById('profile-postal');
    if (postalEl) postalEl.addEventListener('input', () => { postalEdited = true; });
  }

  function init() {
    bindSubmit();
    load();
  }

  return { init, load, submitProfile, fillForm };
})();

// Global alias (POC idiom): app.js bootstraps via window-scope module.
window.profileModule = profileModule;
