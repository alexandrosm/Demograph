"""Render web/index.html headlessly in both width modes, verify, screenshot."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1400})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)
    vals = pg.evaluate(
        '() => [...document.querySelectorAll("text.pop-tick")].map(t => t.textContent)'
    )
    print("pop ticks:", vals)
    pg.screenshot(path="web/preview_full.png", full_page=True)
    # ~1800-2015 CE band (chart y = 24 + (year+2000)/4015 * (H-48), H=5097)
    pg.screenshot(path="web/preview_modern.png", full_page=True,
                  clip={"x": 0, "y": 4880, "width": 1200, "height": 450})
    pg.click("#mode-abs")
    pg.wait_for_timeout(1400)
    pg.screenshot(path="web/preview_full_abs.png", full_page=True)
    b.close()
    print("errors:", errors if errors else "none")
