"""Click a gallery panel on the landing page, then ask the chat in several languages (headless Chromium).
Usage: PYTHONPATH=. python scripts/ops/ui_multilang.py [base_url]"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
QUESTIONS = ["Que signifie ce verset ?", "اس آیت کا کیا مطلب ہے؟", "Bu ayet ne anlatıyor?"]

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1366, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.locator(".gallery-item").nth(4).click(force=True)
    page.wait_for_selector(".info .quran", timeout=120_000)
    print("card:", page.inner_text(".chat-title b"))
    for i, q in enumerate(QUESTIONS):
        page.fill(".ask input", q)
        page.click(".ask .btn.primary")
        done = f"document.querySelectorAll('.bubble.assistant .gen-label').length > {i}"
        page.wait_for_function(done, timeout=120_000)
        last = page.locator(".bubble.assistant").last
        print(f"Q: {q}\n  [{last.locator('.lang-tag').inner_text()}] {last.locator('p').first.inner_text()[:220]}")
    page.wait_for_timeout(800)
    page.screenshot(path="data/ui/multilang.png", full_page=True)
    print("errors:", errors or "none")
    b.close()
