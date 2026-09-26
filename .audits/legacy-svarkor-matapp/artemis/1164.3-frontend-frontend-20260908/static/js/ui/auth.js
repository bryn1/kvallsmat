// ============================================================================
// ui/auth.js — Auth view (login/logout/me) — render-only
// (Phase 8 T7 frontend, gate C7)
// ============================================================================
// Manages the auth view: on init it calls /api/auth/me to learn who is logged in
// (via the opaque HttpOnly session cookie — never visible to JS). If 401 shows
// the login form; if 200 shows the logged-in identity + a logout button.
// On login it POSTs /api/auth/login, then refreshes; on logout it POSTs
// /api/auth/logout and clears. Render-only: it fetches /api/* and draws DOM, and
// never computes auth state itself (REV2 invariant #2) — the backend is the
// sole authority on who is logged in.
// ============================================================================

const authModule = (() => {
  // ---- Data accessors (render-only) ----
  async function fetchMe() {
    const res = await apiGet(Endpoints.me);
    return await res.json(); // {user_id, username}
  }

  async function doLogin(username, password) {
    const res = await apiPost(Endpoints.login, { username, password });
    return await res.json(); // {ok, username}
  }

  async function doLogout() {
    const res = await apiPost(Endpoints.logout, {});
    return await res.json(); // {ok}
  }

  // ---- View switching (auth <-> logged-in) ----
  function showLogin() {
    const loginView = document.getElementById('auth-login');
    const statusView = document.getElementById('auth-status');
    const errEl = document.getElementById('auth-error');
    if (loginView) loginView.hidden = false;
    if (statusView) statusView.hidden = true;
    if (errEl) errEl.hidden = true;
  }

  function showLoggedIn(user) {
    const loginView = document.getElementById('auth-login');
    const statusView = document.getElementById('auth-status');
    const nameEl = document.getElementById('auth-username');
    if (loginView) loginView.hidden = true;
    if (statusView) statusView.hidden = false;
    if (nameEl) nameEl.textContent = (user && user.username) || '';
  }

  // ---- UI feedback helpers ----
  function showError(message) {
    const errEl = document.getElementById('auth-error');
    if (errEl) {
      errEl.textContent = message;
      errEl.hidden = false;
    }
  }

  // ---- Login submit ----
  async function submitLogin() {
    const userEl = document.getElementById('auth-input-user');
    const passEl = document.getElementById('auth-input-pass');
    const username = (userEl && userEl.value || '').trim();
    const password = passEl ? passEl.value : '';
    if (!username || !password) {
      showError('Fyll i användarnamn och lösenord.');
      return;
    }
    try {
      await doLogin(username, password);
      await refreshAuth();
    } catch (err) {
      console.error('Login failed:', err);
      showError('Fel användarnamn eller lösenord.');
    }
  }

  // ---- Logout ----
  async function submitLogout() {
    try {
      await doLogout();
    } catch (err) {
      console.error('Logout failed (continuing):', err);
    }
    await refreshAuth();
  }

  // ---- Fresh auth state from the backend (authority) ----
  async function refreshAuth() {
    try {
      const user = await fetchMe();
      showLoggedIn(user);
    } catch (err) {
      // 401 => not logged in => login view. Any other error also falls back to login.
      showLogin();
    }
  }

  // ---- Wiring ----
  function bindLogin() {
    const form = document.getElementById('auth-form');
    if (form) form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      submitLogin();
    });
  }

  function bindLogout() {
    const btn = document.getElementById('auth-logout');
    if (btn) btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      submitLogout();
    });
  }

  function init() {
    bindLogin();
    bindLogout();
    refreshAuth();
  }

  return { init, refreshAuth, submitLogin, submitLogout, showLogin, showLoggedIn };
})();

// Global alias (POC idiom): app.js bootstraps via window-scope module.
window.authModule = authModule;
