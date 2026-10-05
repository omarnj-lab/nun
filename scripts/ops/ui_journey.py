"""Gallery panel → guess before reading → Explore tabs (why, quiz, map, journey) → next stop (headless Chromium).
Usage: PYTHONPATH=. python scripts/ops/ui_journey.py [base_url] [--phone]"""

import sys

from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8000")
PHONE = "--phone" in sys.argv
tag = "phone" if PHONE else "desktop"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(**(p.devices["Pixel 7"] if PHONE else {"viewport": {"width": 1366, "height": 900}}))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.locator(".gallery-item").nth(4).dispatch_event("click")  # 15_forest_gold → 97:1
    page.wait_for_selector(".pre-guess", timeout=120_000)
    page.screenshot(path=f"data/ui/{tag}_j1_guess.png", full_page=True)
    page.locator(".pre-guess .option").first.click()
    page.wait_for_selector(".translation.reveal")
    tabs = page.locator(".tabs button")
    tabs.nth(3).click()
    page.wait_for_selector(".mv-lines line")
    print("why: match lines", page.locator(".mv-lines line").count())
    tabs.nth(2).click()
    page.wait_for_selector(".qmap-bars i")
    print("map: surahs", page.locator(".qmap-bars i").count())
    tabs.nth(1).click()
    for q in range(3):
        page.locator(".quiz-q").nth(q).locator(".option").first.click()
    page.wait_for_selector(".quiz-result")
    print("quiz:", page.inner_text(".quiz-result b"))
    page.locator(".next-step").click()
    page.wait_for_selector(".stop, .journey")
    print("passport:", page.inner_text(".passport-head span"))
    page.wait_for_timeout(800)
    page.screenshot(path=f"data/ui/{tag}_j2_card.png", full_page=True)
    if PHONE:
        print("ask bar visible:", page.locator(".ask-bar .btn").is_visible())
    stops = page.locator(".stop")
    if stops.count():
        stops.first.click()
        page.wait_for_selector(".pre-guess", timeout=120_000)
        print("next stop card:", page.locator(".tiles .tile-value").nth(1).inner_text())
    print("errors:", errors or "none")
    b.close()
