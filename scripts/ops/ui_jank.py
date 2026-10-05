"""Jank check with a 4× slower CPU (mid-range phone): long tasks (> 50 ms) and frame times while loading,
scanning and scrolling. Usage: PYTHONPATH=. python scripts/ops/ui_jank.py [base_url]"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PROBE = """() => { window.__lt = []; new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration)))
  .observe({type: 'longtask', buffered: true}); }"""
FRAMES = """async (ms) => { const t = []; let last = performance.now(); const end = last + ms;
  await new Promise(res => { const f = now => { t.push(now - last); last = now; now < end ? requestAnimationFrame(f) : res(); };
  requestAnimationFrame(f); }); t.sort((a, b) => a - b);
  return {frames: t.length, p50: Math.round(t[t.length >> 1]), p95: Math.round(t[Math.floor(t.length * .95)]), max: Math.round(t[t.length - 1])}; }"""


def report(page, label):
    lt = page.evaluate("window.__lt || []")
    print(f"{label:10s} long tasks: {len(lt)}  total {round(sum(lt))} ms  max {round(max(lt or [0]))} ms")
    page.evaluate("window.__lt = []")


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 412, "height": 900}, is_mobile=True, has_touch=True)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    page.add_init_script(PROBE.replace("() => {", "(() => {") + ")()")
    page.goto(BASE, wait_until="networkidle")
    report(page, "landing")
    print("  idle frames", page.evaluate(FRAMES, 1500))
    page.mouse.wheel(0, 3000)
    print("  scroll frames", page.evaluate(FRAMES, 1500))
    report(page, "scroll")
    page.locator(".gallery-item").nth(4).dispatch_event("click")
    page.wait_for_selector(".info .quran", timeout=120_000)
    page.wait_for_timeout(3000)
    report(page, "result")
    print("  idle frames", page.evaluate(FRAMES, 1500))
    for _ in range(4):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(150)
    print("  scroll frames", page.evaluate(FRAMES, 1500))
    report(page, "scroll")
    b.close()
