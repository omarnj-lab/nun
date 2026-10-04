"""Drive the real web app in headless Chromium: upload a photo → card → chat → ask a question.
Prints browser console errors and saves screenshots to data/ui/. Usage:
    PYTHONPATH=. python scripts/ops/ui_check.py [base_url] [photo] [--desktop]
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8000"
DEFAULT_PHOTO = "data/real_test/queries/real_ayat_alkursi__1.jpg"
PHOTO = next((a for a in sys.argv[1:] if not a.startswith(("http", "--"))), DEFAULT_PHOTO)
DESKTOP = "--desktop" in sys.argv
OUT = Path("data/ui")
OUT.mkdir(parents=True, exist_ok=True)
tag = "desktop" if DESKTOP else "phone"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(**({"viewport": {"width": 1366, "height": 860}} if DESKTOP else p.devices["Pixel 7"]))
    page = ctx.new_page()
    errors = []
    page.on(
        "console",
        lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None,
    )
    page.on("pageerror", lambda e: errors.append(f"PAGE ERROR: {e}"))
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / f"{tag}_1_home.png", full_page=True)
    page.locator("input[type=file]").last.set_input_files(PHOTO)
    page.wait_for_selector(".quran, .notice", timeout=120_000)
    page.wait_for_timeout(800)
    page.screenshot(path=OUT / f"{tag}_2_result.png", full_page=True)
    ask = page.locator("text=/اسأل عن هذه الآية|Ask about this verse/")
    if ask.count():
        ask.first.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=OUT / f"{tag}_3_chat.png", full_page=True)
        body_text = page.inner_text("body")
        print("chat page text length:", len(body_text))
        page.locator(".suggest .bubble-btn").first.click()
        try:
            page.wait_for_selector(".bubble.assistant .gen-label", timeout=120_000)
        except Exception as e:  # noqa: BLE001
            errors.append(f"no answer rendered: {type(e).__name__}")
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / f"{tag}_4_answer.png", full_page=True)
        print("body after answer (first 300 chars):", page.inner_text("body")[:300].replace("\n", " | "))
    print("errors:", errors or "none")
    b.close()
