"""Recitation on the calligraphy: play the recitation and sample which word / photo region is lit over time."""

import sys

from playwright.sync_api import sync_playwright

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8000")
PHOTO = next(
    (a for a in sys.argv[1:] if not a.startswith(("http", "--"))), "data/real_test/queries/real_ayat_alkursi__1.jpg"
)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = b.new_page(viewport={"width": 1366, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.locator("input[type=file]").last.set_input_files(PHOTO)
    page.wait_for_selector(".region-badge", timeout=120_000)
    page.locator(".player .play").click()
    seen = []
    for k in range(10):
        page.wait_for_timeout(2500)
        word = page.locator(".w.sung")
        region = page.evaluate(
            "Array.from(document.querySelectorAll('rect.region')).findIndex(r => r.classList.contains('singing'))"
        )
        seen.append((round(2.5 * (k + 1), 1), word.inner_text() if word.count() else None, region))
        if k == 3:
            page.screenshot(path="data/ui/karaoke.png")
    print(
        page.evaluate(
            "Array.from(document.querySelectorAll('rect.region')).map(r => [r.getAttribute('x'), r.getAttribute('y'), r.getAttribute('width'), r.getAttribute('height')].map(v => (+v).toFixed(2)).join(','))"
        )
    )
    for s in seen:
        print(s)
    print("errors:", errors or "none")
    b.close()
