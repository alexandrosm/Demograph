"""Count rendered event annotations and capture a classical-era close-up."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1400})
    pg.goto(url)
    pg.wait_for_timeout(2500)
    n = pg.evaluate("() => document.querySelectorAll('text.event-label').length")
    print("events rendered:", n)
    print("stats:", pg.evaluate("() => window._evStats"))
    pg.screenshot(path="web/preview_events.png", full_page=True,
                  clip={"x": 0, "y": 2280, "width": 1200, "height": 700})
    b.close()
