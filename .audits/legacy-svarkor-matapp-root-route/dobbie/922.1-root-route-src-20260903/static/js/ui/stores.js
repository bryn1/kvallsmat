// ============================================================================
// ui/stores.js — Store pick view (render-only)
// ============================================================================
// Fetches /api/stores and /api/stores/selected, renders picker cards, and on
// save POSTs the selection to /api/stores/select. Render-only: it draws the DOM
// from backend data and never computes menu/business state (REV2 invariant #2).
//
// Max selectable stores is a HARD cap of 3 (the backend rejects >3 with 422);
// the UI reflects + prevents it client-side for better UX, never silently.
// ============================================================================

const storesModule = (() => {
  const MAX_SELECTED = 3;

  // ---- State (transport-only: which store cards the user has clicked) ----
  let allStores = [];
  let selectedIds = new Set();

  // ---- Data accessors (render-only) ----
  async function fetchStores() {
    try {
      const res = await apiGet(Endpoints.stores);
      return await res.json();
    } catch (err) {
      console.error('Failed to load stores:', err);
      throw err;
    }
  }

  async function fetchSelected() {
    try {
      const res = await apiGet(Endpoints.storeSelected);
      const rows = await res.json(); // [{store_id, selected_at}]
      return (Array.isArray(rows) ? rows : []).map((r) => r.store_id);
    } catch (err) {
      console.error('Failed to load selected stores:', err);
      return [];
    }
  }

  async function saveSelection(storeIds) {
    const res = await apiPost(Endpoints.storeSelect, { store_ids: storeIds });
    return await res.json(); // {selected: [store_id,...]}
  }

  // ---- Rendering: single store card ----
  function renderStoreCard(store) {
    const checked = selectedIds.has(store.store_id);
    return `
      <label class="store-card${checked ? ' store-card--selected' : ''}"
             data-store-id="${store.store_id}">
        <span class="store-card__control">
          <input type="checkbox"
                 class="store-card__checkbox"
                 value="${store.store_id}"
                 ${checked ? 'checked' : ''}
                 aria-label="Välj ${store.name}">
        </span>
        <span class="store-card__body">
          <span class="store-card__name">${store.name}
            <span class="store-card__chain">${store.chain_type || ''}</span>
          </span>
        </span>
      </label>`;
  }

  // ---- Rendering: full list ----
  function renderStores() {
    const fieldset = document.getElementById('stores-fieldset');
    const form = document.getElementById('stores-form');
    const empty = document.getElementById('stores-empty');
    if (!fieldset) return;

    if (allStores.length === 0) {
      // Successful fetch, but no stores: clear loading, show empty state.
      setBanner('empty');
      return;
    }

    fieldset.innerHTML = allStores.map(renderStoreCard).join('');
    if (form) form.hidden = false;
    if (empty) empty.hidden = true;
    const loading = document.getElementById('stores-loading');
    const error = document.getElementById('stores-error');
    if (loading) loading.hidden = true;
    if (error) error.hidden = true;

    wireCardEvents();
    updateSaveState();
  }

  // ---- Wiring card checkbox behaviour ----
  function wireCardEvents() {
    const cards = document.querySelectorAll('.store-card__checkbox');
    cards.forEach((cb) => {
      cb.addEventListener('change', (ev) => {
        const id = ev.target.value;
        const wasChecked = ev.target.checked;
        // Enforce hard cap of 3.
        if (wasChecked && selectedIds.size >= MAX_SELECTED) {
          ev.target.checked = false;
          updateSaveState();
          return;
        }
        if (wasChecked) {
          selectedIds.add(id);
        } else {
          selectedIds.delete(id);
        }
        // Reflect selected state on the card chrome.
        const card = ev.target.closest('.store-card');
        if (card) card.classList.toggle('store-card--selected', wasChecked);
        updateSaveState();
      });
    });
  }

  // ---- Update hint text + save button disabled state ----
  function updateSaveState() {
    const saveBtn = document.getElementById('stores-save');
    const hint = document.getElementById('stores-hint');
    if (saveBtn) saveBtn.disabled = selectedIds.size === 0;
    if (hint) {
      if (selectedIds.size === 0) {
        hint.textContent = 'Välj minst en butik för att spara.';
      } else if (selectedIds.size >= MAX_SELECTED) {
        hint.textContent = `${selectedIds.size}/${MAX_SELECTED} valda — max ${MAX_SELECTED} butiker.`;
      } else {
        hint.textContent = `${selectedIds.size}/${MAX_SELECTED} valda.`;
      }
    }
  }

  function setBanner(which) {
    const loading = document.getElementById('stores-loading');
    const error = document.getElementById('stores-error');
    const empty = document.getElementById('stores-empty');
    const form = document.getElementById('stores-form');
    if (loading) loading.hidden = which !== 'loading';
    if (error) error.hidden = which !== 'error';
    if (empty) empty.hidden = which !== 'empty';
    // Form is only ever shown by renderStores() on the success path; every
    // banner state keeps it hidden.
    if (form) form.hidden = true;
  }

  function bindSave() {
    const form = document.getElementById('stores-form');
    if (!form) return;
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (selectedIds.size === 0) return;
      const storeIds = Array.from(selectedIds);
      const saveBtn = document.getElementById('stores-save');
      const origLabel = saveBtn ? saveBtn.textContent : '';
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Sparar...';
      }
      try {
        const result = await saveSelection(storeIds);
        const saved = Array.isArray(result.selected) ? result.selected : [];
        selectedIds = new Set(saved);
        renderStores();
        // Surface success through a gentle inline message when available.
        const hint = document.getElementById('stores-hint');
        if (hint) hint.textContent = `Sparat: ${saved.length} butiker valda.`;
      } catch (err) {
        console.error('Failed to save stores:', err);
        const hint = document.getElementById('stores-hint');
        if (hint) hint.textContent = 'Kunde inte spara urvalet — försök igen.';
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = origLabel;
        }
      }
    });
  }

  function bindRetry() {
    const btn = document.getElementById('stores-retry');
    if (btn) btn.addEventListener('click', loadStores);
  }

  // ---- Public API ----
  async function loadStores() {
    setBanner('loading');
    try {
      const [stores, selected] = await Promise.all([
        fetchStores(),
        fetchSelected(),
      ]);
      allStores = Array.isArray(stores) ? stores : [];
      selectedIds = new Set(selected.filter((id) =>
        allStores.some((s) => String(s.store_id) === String(id))
      ));
      renderStores();
    } catch (err) {
      console.error('Failed to load store view:', err);
      setBanner('error');
    }
  }

  function init() {
    bindSave();
    bindRetry();
    loadStores();
  }

  function getStores() { return allStores; }
  function getSelectedIds() { return Array.from(selectedIds); }

  return { init, loadStores, getStores, getSelectedIds, MAX_SELECTED };
})();

// Global alias (Hotell idiom): app.js bootstraps via window-scope module.
window.storesModule = storesModule;
