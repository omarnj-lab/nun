"""Render a Naskh test panel that is NOT in the collection (verse text verbatim from the corpus, Amiri font), for
end-to-end tests of the reading path. Output: data/ui/test_naskh_<sura>_<aya>.png (git-ignored)."""

import sys

from playwright.sync_api import sync_playwright

from nun.corpus.store import CorpusStore

sura, aya = (int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "39:53").split(":"))
text = CorpusStore().get(sura, aya).text_uthmani_tanzil
html = f"""<html><head><link href="https://fonts.googleapis.com/css2?family=Amiri:wght@700&display=swap" rel="stylesheet"></head>
<body style="margin:0;background:#efe6d2;display:grid;place-items:center;width:1200px;height:900px">
<div style="width:1000px;padding:60px;border:10px double #8a6a2c;border-radius:24px;background:#f7f0e0;
font-family:Amiri;font-weight:700;font-size:64px;line-height:1.9;color:#1d2a44;text-align:center" dir="rtl">{text}</div>
</body></html>"""
out = f"data/ui/test_naskh_{sura}_{aya}.png"
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1200, "height": 900})
    page.set_content(html, wait_until="networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=out)
    b.close()
print(out)
