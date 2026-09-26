from playwright.sync_api import sync_playwright
BASE = "https://sibbamala.com/matapp/"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for vw,vh,label in [(1280,900,"desktop"),(360,800,"mobile-360"),(320,700,"mobile-320")]:
        ctx = browser.new_context(viewport={"width":vw,"height":vh})
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1200)
        # select stores, save, generate menu
        for cb in page.query_selector_all(".store-card__checkbox"):
            try: cb.check()
            except Exception: pass
        page.click("#stores-save"); page.wait_for_timeout(1000)
        page.click("a[data-page=menu]")
        page.fill("#menu-week","2026-W37")
        page.click("#menu-submit"); page.wait_for_timeout(2000)
        # check every element for horizontal overflow / clipped text
        issues = page.evaluate("""() => {
          const out = [];
          const docW = document.documentElement.clientWidth;
          document.querySelectorAll('body *').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0) {
              if (r.right > docW + 1 || r.left < -1) {
                out.push(`OVERFLOW ${el.tagName}.${el.className} right=${r.right.toFixed(0)} docW=${docW}`);
              }
              // scrollWidth > clientWidth means clipped content inside
              if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
                  getComputedStyle(el).overflowX !== 'auto' && getComputedStyle(el).overflowX !== 'scroll' &&
                  el.tagName !== 'SELECT' && el.tagName !== 'INPUT') {
                out.push(`CLIPPED ${el.tagName}.${el.className} scrollW=${el.scrollWidth} clientW=${el.clientWidth} text=${(el.textContent||'').slice(0,40)}`);
              }
            }
          });
          return out;
        }""")
        print(f"=== {label} ({vw}px): {len(issues)} issues")
        for i in issues[:20]: print("  ", i)
        ctx.close()
    browser.close()
print("OVERFLOW_CHECK_EXIT=0")
