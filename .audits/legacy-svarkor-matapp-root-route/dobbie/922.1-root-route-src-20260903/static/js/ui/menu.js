// ============================================================================
// ui/menu.js — Weekly menu view (render-only)
// ============================================================================
// Reads the constraints form, builds the query string, GETs /api/menu and
// renders ONE card per day ({date, dish_id}) with offer badges from
// used_offer_ids. 0-offer days render recipe-only, never assuming
// used_offer_ids is non-empty (REV2 R4 — VERIFIED 0-offer degrade).
//
// Render-only: it fetches /api/* and draws the DOM, and never computes menus
// or holds business state (REV2 invariant #2).
// ============================================================================

const menuModule = (() => {
  // ---- Swedish weekday labels (ISO Monday-first) ----
  const WEEKDAY_LABELS = {
    1: 'Måndag', 2: 'Tisdag', 3: 'Onsdag', 4: 'Torsdag',
    5: 'Fredag', 6: 'Lördag', 7: 'Söndag',
  };

  // ---- Constraint form → query params ----
  function buildQuery(weekValue) {
    // Week is required by the router and validated with ^\d{4}-W\d{1,2}$.
    const params = new URLSearchParams();
    params.set('week', weekValue);

    const mealDays = document.getElementById('menu-meal-days')?.value;
    if (mealDays) params.set('meal_days', mealDays);

    const persons = document.getElementById('menu-persons')?.value;
    if (persons) params.set('persons', persons);

    const vegetarian = document.getElementById('menu-vegetarian')?.checked;
    if (vegetarian) params.set('vegetarian', 'true');

    const budget = document.getElementById('menu-budget')?.value;
    if (budget) params.set('budget_tier', budget);

    const allergens = document.getElementById('menu-allergens')?.selectedOptions;
    if (allergens && allergens.length > 0) {
      for (const opt of allergens) params.append('allergens', opt.value);
    }

    const seed = document.getElementById('menu-seed')?.value;
    if (seed) params.set('seed', seed);

    return params.toString();
  }

  // ---- Data accessor (render-only) ----
  async function fetchMenu(queryString) {
    try {
      const res = await apiGet(`${Endpoints.menu}?${queryString}`);
      return await res.json();
    } catch (err) {
      console.error('Failed to load menu:', err);
      throw err;
    }
  }

  // ---- Formatting date for Swedish display ----
  function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function weekdayOf(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    if (Number.isNaN(d.getTime())) return '';
    const iso = d.getDay() === 0 ? 7 : d.getDay();
    return WEEKDAY_LABELS[iso] || '';
  }

  // ---- Offer badges from used_offer_ids (REV2 R4 degrade) ----
  function renderOfferBadges(usedOfferIds) {
    const ids = Array.isArray(usedOfferIds) ? usedOfferIds : [];
    if (ids.length === 0) {
      // 0-offer day: render recipe-only fallback chip — never assume non-empty.
      return `<div class="offer-list" aria-label="Inga erbjudanden">
        <span class="offer-badge offer-badge--zero">Inga erbjudanden</span>
      </div>`;
    }
    const total = ids.length;
    return `<div class="offer-list" aria-label="${total} erbjudande${total === 1 ? '' : 'n'} kopplade">
      <span class="offer-badge"><span class="offer-badge__count">${total}</span> erbjudande${total === 1 ? '' : 'n'}</span>
    </div>`;
  }

  // ---- Rendering: single day card ----
  function renderDayCard(day) {
    const date = day && day.date ? day.date : '';
    const dish = day && day.dish_id ? day.dish_id : 'Recept saknas';
    const offers = day ? day.used_offer_ids : [];

    return `<article class="day-card" role="listitem">
      <header class="day-card__heading">
        <span class="day-card__date">${formatDate(date)}</span>
        <span class="day-card__weekday">${weekdayOf(date)}</span>
      </header>
      <h3 class="day-card__dish">${dish}</h3>
      <h4 class="day-card__offers-heading">Erbjudanden</h4>
      ${renderOfferBadges(offers)}
    </article>`;
  }

  // ---- Rendering: full set of day cards ----
  function renderMenu(menuData) {
    const days = (menuData && Array.isArray(menuData.days)) ? menuData.days : [];
    const results = document.getElementById('menu-results');
    const weekKeyEl = document.getElementById('menu-week-key');
    const countEl = document.getElementById('menu-day-count');
    const grid = document.getElementById('menu-days');
    const loadingEl = document.getElementById('menu-days-loading');
    const emptyEl = document.getElementById('menu-days-empty');
    const topLoadingEl = document.getElementById('menu-loading');

    if (weekKeyEl) weekKeyEl.textContent = menuData && menuData.week_key
      ? `Vecka ${menuData.week_key}`
      : 'Veckomeny';
    if (countEl) countEl.textContent = days.length
      ? `${days.length} middagar`
      : '';

    if (grid) grid.innerHTML = days.map(renderDayCard).join('');
    if (loadingEl) loadingEl.hidden = true;
    if (topLoadingEl) topLoadingEl.hidden = true;
    if (emptyEl) emptyEl.hidden = days.length > 0;
    if (results) results.hidden = false;
  }

  // ---- Banner / state switching ----
  function setMenuBanner(which) {
    const loading = document.getElementById('menu-loading');
    const error = document.getElementById('menu-error');
    const results = document.getElementById('menu-results');
    if (loading) loading.hidden = which !== 'loading';
    if (error) error.hidden = which !== 'error';
    if (results) results.hidden = (which === 'loading' || which === 'error');
  }

  // ---- Submit flow ----
  async function submitMenu() {
    const weekValue = document.getElementById('menu-week')?.value?.trim();
    if (!weekValue) {
      const errEl = document.getElementById('menu-error-text');
      if (errEl) errEl.textContent = 'Ange en vecka, t.ex. 2026-W34.';
      setMenuBanner('error');
      return;
    }
    setMenuBanner('loading');
    try {
      const qs = buildQuery(weekValue);
      const data = await fetchMenu(qs);
      renderMenu(data);
    } catch (err) {
      console.error('Failed to load menu view:', err);
      const errEl = document.getElementById('menu-error-text');
      if (errEl) {
        errEl.textContent = 'Kunde inte hämta veckomenyn. Kontrollera att du valt butiker och att veckan är giltig, och försök igen.';
      }
      setMenuBanner('error');
    }
  }

  function bindForm() {
    const form = document.getElementById('menu-form');
    if (form) form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      submitMenu();
    });
  }

  function bindRetry() {
    const btn = document.getElementById('menu-retry');
    if (btn) btn.addEventListener('click', submitMenu);
  }

  // ---- Public API ----
  function init() {
    bindForm();
    bindRetry();
  }

  return {
    init,
    submitMenu,
    buildQuery,
    renderDayCard,
    renderOfferBadges,
    renderMenu,
  };
})();

// Global alias (Hotell idiom): app.js bootstraps via window-scope module.
window.menuModule = menuModule;
