import json, sys
from playwright.sync_api import sync_playwright

BASE = "https://sibbamala.com/matapp/"
results = {"console": [], "pageerrors": [], "requests": [], "clicks": []}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()

    page.on("console", lambda m: results["console"].append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: results["pageerrors"].append(str(e)))
    page.on("response", lambda r: results["requests"].append(f"{r.status} {r.url}"))

    # STEP 1: navigate, console first
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    print("=== TITLE ===", page.title())
    print("=== CONSOLE AFTER LOAD ===")
    for c in results["console"]: print(" ", c)
    print("=== PAGE ERRORS ===", results["pageerrors"])
    print("=== FAILED REQUESTS (>=400) ===")
    for r in results["requests"]:
        code = int(r.split(" ")[0])
        if code >= 400: print(" ", r)

    # snapshot of stores view
    print("=== STORES VIEW: visible elements ===")
    print("stores-loading hidden:", page.eval_on_selector("#stores-loading", "e => e.hidden"))
    print("stores-error hidden:", page.eval_on_selector("#stores-error", "e => e.hidden"))
    print("stores-form hidden:", page.eval_on_selector("#stores-form", "e => e.hidden"))
    cards = page.query_selector_all(".store-card")
    print("store cards rendered:", len(cards))
    for c in cards:
        print("  card:", c.inner_text().replace("\n", " | "))
    checkboxes = page.query_selector_all(".store-card__checkbox")
    print("checkboxes:", len(checkboxes))
    save_disabled = page.eval_on_selector("#stores-save", "e => e.disabled")
    hint = page.inner_text("#stores-hint")
    print("save disabled:", save_disabled, "| hint:", repr(hint))

    # screenshot start view
    page.screenshot(path="shot1-stores-desktop.png", full_page=True)

    # CLICK-THROUGH: every interactive element
    def click_log(name, fn):
        before = len(results["console"])
        try:
            fn()
            page.wait_for_timeout(800)
            new_console = results["console"][before:]
            print(f"CLICK {name}: OK; new console: {new_console if new_console else 'none'}")
            results["clicks"].append((name, "OK", new_console))
        except Exception as e:
            print(f"CLICK {name}: EXCEPTION {e}")
            results["clicks"].append((name, "EXC", str(e)))

    # 1. nav links
    click_log("nav 'Veckomeny'", lambda: page.click("a[data-page=menu]"))
    print("  page-stores hidden:", page.eval_on_selector("#page-stores", "e => e.hidden"))
    print("  page-menu hidden:", page.eval_on_selector("#page-menu", "e => e.hidden"))
    page.screenshot(path="shot2-menu-desktop.png", full_page=True)
    click_log("nav 'Butiker'", lambda: page.click("a[data-page=stores]"))
    print("  page-stores hidden:", page.eval_on_selector("#page-stores", "e => e.hidden"))

    # 2. store checkboxes: select 3, try 4th
    for i, cb in enumerate(checkboxes):
        click_log(f"store checkbox {i} ({cb.get_attribute('value')})",
                  lambda cb=cb: cb.check())
    print("  hint after 3 selected:", repr(page.inner_text("#stores-hint")))
    print("  save disabled:", page.eval_on_selector("#stores-save", "e => e.disabled"))
    page.screenshot(path="shot3-stores-selected.png", full_page=True)

    # 3. save selection
    click_log("stores-save (submit)", lambda: page.click("#stores-save"))
    page.wait_for_timeout(1200)
    print("  hint after save:", repr(page.inner_text("#stores-hint")))
    print("  selected via API check next...")

    # 4. menu form interactions
    click_log("nav 'Veckomeny' again", lambda: page.click("a[data-page=menu]"))
    page.fill("#menu-week", "2026-W37")
    page.select_option("#menu-meal-days", "5")
    page.select_option("#menu-persons", "2")
    page.select_option("#menu-budget", "mid")
    click_log("menu-submit (valid week)", lambda: page.click("#menu-submit"))
    page.wait_for_timeout(2500)
    print("  menu-results hidden:", page.eval_on_selector("#menu-results", "e => e.hidden"))
    print("  menu-error hidden:", page.eval_on_selector("#menu-error", "e => e.hidden"))
    print("  week-key:", repr(page.inner_text("#menu-week-key")))
    print("  day-count:", repr(page.inner_text("#menu-day-count")))
    days = page.query_selector_all(".day-card")
    print("  day cards:", len(days))
    for d in days[:3]:
        print("   ", d.inner_text().replace("\n", " | "))
    page.screenshot(path="shot4-menu-generated.png", full_page=True)

    # 5. empty week -> error path
    page.fill("#menu-week", "")
    click_log("menu-submit (empty week)", lambda: page.click("#menu-submit"))
    page.wait_for_timeout(800)
    print("  menu-error-text:", repr(page.inner_text("#menu-error-text")))

    # 6. invalid week -> 422 path
    page.fill("#menu-week", "banana")
    click_log("menu-submit (invalid week 'banana')", lambda: page.click("#menu-submit"))
    page.wait_for_timeout(1200)
    print("  menu-error-text:", repr(page.inner_text("#menu-error-text")))
    print("  menu-error visible:", not page.eval_on_selector("#menu-error", "e => e.hidden"))
    page.screenshot(path="shot5-menu-error.png", full_page=True)

    # 7. retry button
    click_log("menu-retry", lambda: page.click("#menu-retry"))
    page.wait_for_timeout(1500)
    print("  after retry, error hidden:", page.eval_on_selector("#menu-error", "e => e.hidden"))

    # 8. stores-retry button
    click_log("nav 'Butiker'", lambda: page.click("a[data-page=stores]"))
    click_log("stores-retry", lambda: page.click("#stores-retry"))
    page.wait_for_timeout(1500)
    print("  stores-error hidden after retry:", page.eval_on_selector("#stores-error", "e => e.hidden"))

    # 9. narrow viewport (mobile 360px) — SPEC
    page.set_viewport_size({"width": 360, "height": 800})
    page.wait_for_timeout(500)
    page.screenshot(path="shot6-stores-mobile360.png", full_page=True)
    # check horizontal overflow
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    print("MOBILE 360px horizontal overflow:", overflow)
    click_log("nav 'Veckomeny' (mobile)", lambda: page.click("a[data-page=menu]"))
    page.screenshot(path="shot7-menu-mobile360.png", full_page=True)
    overflow2 = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    print("MOBILE 360px menu-view horizontal overflow:", overflow2)
    # allergens multi-select size=6 at 360px
    box = page.eval_on_selector("#menu-allergens", "e => { const r = e.getBoundingClientRect(); return {w: r.width, h: r.height}; }")
    print("allergens select box at 360px:", box)

    # final console dump
    print("=== FULL CONSOLE LOG (end) ===")
    for c in results["console"]: print(" ", c)
    print("=== ALL PAGE ERRORS ===", results["pageerrors"])
    print("=== ALL >=400 RESPONSES ===")
    for r in results["requests"]:
        if int(r.split(" ")[0]) >= 400: print(" ", r)

    browser.close()
print("AUDIT_RUN_EXIT=0")
