"""Click «try a sample panel» on the landing page and check that the verse card appears (headless Chromium)."""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1366, "height": 860})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.click(".sample-link")
    page.wait_for_timeout(600)
    page.screenshot(path="data/ui/sample_scanning.png")
    page.wait_for_selector(".info .quran", timeout=120_000)
    print("card:", page.inner_text(".chat-title b"))
    print("errors:", errors or "none")
    b.close()
