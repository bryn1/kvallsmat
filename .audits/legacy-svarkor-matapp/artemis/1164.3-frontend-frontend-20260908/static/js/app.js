// ============================================================================
// app.js — Bootstrap (view switching) — matapp framtidsvision Phase 8 frontend
// ============================================================================
// Runs after ui modules are loaded (they register their logic): wires the nav
// tabs, shows the auth view by default, and calls each module's init.
// No inline handlers in the markup — all wiring lives here.
// ============================================================================

(function bootstrap() {
  const navLinks = document.querySelectorAll('.site-nav__link[data-page]');
  const views = {
    auth: document.getElementById('page-auth'),
    profile: document.getElementById('page-profile'),
    suggestions: document.getElementById('page-suggestions'),
  };

  function switchView(pageId) {
    // Update nav active state.
    navLinks.forEach((link) => {
      const active = link.dataset.page === pageId;
      link.classList.toggle('site-nav__link--active', active);
      link.setAttribute('aria-current', active ? 'page' : 'false');
    });
    // Show the selected view only.
    Object.entries(views).forEach(([id, el]) => {
      if (el) el.hidden = id !== pageId;
    });
    // Refresh the view's data when it becomes visible (profile/suggestions).
    if (pageId === 'profile' && window.profileModule) profileModule.load();
    if (pageId === 'suggestions' && window.suggestionsModule) suggestionsModule.load();
  }

  navLinks.forEach((link) => {
    link.addEventListener('click', (ev) => {
      ev.preventDefault();
      const pageId = link.dataset.page;
      if (views[pageId]) switchView(pageId);
    });
  });

  // Register module init only once after DOM is ready.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }

  function run() {
    if (window.authModule && typeof authModule.init === 'function') authModule.init();
    if (window.profileModule && typeof profileModule.init === 'function') profileModule.init();
    if (window.suggestionsModule && typeof suggestionsModule.init === 'function') suggestionsModule.init();
  }
})();
