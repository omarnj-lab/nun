"""Idle rendering cost of the landing and result pages (Chrome DevTools metrics over 3 s). Lower is smoother.
Usage: PYTHONPATH=. python scripts/ops/ui_perf.py [base_url]"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def sample(page, cdp, label: str) -> None:
    def m() -> dict:
        return {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}

    a = m()
    page.wait_for_timeout(3000)
    b = m()
    keys = [
        "LayoutCount",
        "RecalcStyleCount",
        "LayoutDuration",
        "RecalcStyleDuration",
        "ScriptDuration",
        "TaskDuration",
    ]
    print(label, {k: round(b[k] - a[k], 3) for k in keys})


with sync_playwright() as p:
    br = p.chromium.launch()
    page = br.new_page(viewport={"width": 1366, "height": 900})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Performance.enable")
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1500)
    sample(page, cdp, "landing")
    page.locator(".gallery-item").first.click(force=True)
    page.wait_for_selector(".info .quran", timeout=120_000)
    page.wait_for_selector(".region-badge", timeout=120_000)
    sample(page, cdp, "result ")
    br.close()
