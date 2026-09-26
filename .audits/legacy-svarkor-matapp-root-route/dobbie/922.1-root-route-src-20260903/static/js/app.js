// ============================================================================
// app.js — Bootstrap (view switching)
// ============================================================================
// Runs after ui modules are loaded (they register their logic): wires the nav
// tabs, shows the stores view by default, and calls each module's init.
// No inline handlers in the markup — all wiring lives here.
// ============================================================================

(function bootstrap() {
  const navLinks = document.querySelectorAll('.site-nav__link[data-page]');
  const views = {
    stores: document.getElementById('page-stores'),
    menu: document.getElementById('page-menu'),
  };

  function switchView(pageId) {
    // Update nav active state.
    navLinks.forEach((link) => {
      const active = link.dataset.page === pageId;
      link.classList.toggle('site-nav__link--active', active);
      link.setAttribute('aria-current', active ? 'page' : 'false');
    });
    // Show the selected view only.
    if (views.stores) views.stores.hidden = pageId !== 'stores';
    if (views.menu) views.menu.hidden = pageId !== 'menu';
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
    if (window.storesModule && typeof storesModule.init === 'function') {
      storesModule.init();
    }
    if (window.menuModule && typeof menuModule.init === 'function') {
      menuModule.init();
    }
  }
})();
