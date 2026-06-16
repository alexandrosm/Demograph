"""Screenshot every color scheme + the hide-stateless mode."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1400})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2200)
    for key in ("civ", "print", "night", "pastel",
                "age", "glass", "strata", "cyan", "neon"):
        pg.select_option("#scheme", key)
        pg.wait_for_timeout(700)
        pg.screenshot(path=f"web/scheme_{key}.png", full_page=True,
                      clip={"x": 0, "y": 3380, "width": 1200, "height": 620})
    pg.select_option("#scheme", "civ")
    pg.check("#nogray")
    pg.wait_for_timeout(1400)
    pg.screenshot(path="web/scheme_nogray.png", full_page=True)
    b.close()
    print("errors:", errors if errors else "none")
