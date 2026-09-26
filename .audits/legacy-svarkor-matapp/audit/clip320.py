from playwright.sync_api import sync_playwright
BASE = "https://sibbamala.com/matapp/"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width":320,"height":700})
    page = ctx.new_page()
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1200)
    for cb in page.query_selector_all(".store-card__checkbox"):
        try: cb.check()
        except Exception: pass
    page.click("#stores-save"); page.wait_for_timeout(1000)
    page.click("a[data-page=menu]")
    page.fill("#menu-week","2026-W37")
    page.click("#menu-submit"); page.wait_for_timeout(2000)
    detail = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('.day-card, .menu-grid, .day-card__dish, .offer-badge, .constraints-form__grid, .form-field').forEach(el => {
        const r = el.getBoundingClientRect();
        out.push(`${el.tagName}.${el.className} left=${r.left.toFixed(1)} right=${r.right.toFixed(1)} w=${r.width.toFixed(1)} scrollW=${el.scrollWidth}`);
      });
      return out;
    }""")
    for d in detail: print("  ", d)
    page.screenshot(path="shot8-menu-mobile320.png", full_page=True)
    browser.close()
print("CLIP320_EXIT=0")
