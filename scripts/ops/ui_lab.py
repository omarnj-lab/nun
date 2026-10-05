"""KhaṭṭVision Lab: open from the header, run the sample panel, check the output (headless Chromium)."""

import sys

from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8000")
PHONE = "--phone" in sys.argv
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(**(p.devices["Pixel 7"] if PHONE else {"viewport": {"width": 1366, "height": 900}}))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.click(".lab-link")
    page.wait_for_selector(".lab-hero")
    page.locator(".lab-try .cta").nth(1).click()
    page.wait_for_selector(".lab-dl", timeout=120_000)
    page.wait_for_timeout(1500)
    print("lab:", page.inner_text(".lab-dl").replace("\n", " | ")[:300])
    page.screenshot(path=f"data/ui/{'phone' if PHONE else 'desktop'}_lab.png", full_page=True)
    print("errors:", errors or "none")
    b.close()
