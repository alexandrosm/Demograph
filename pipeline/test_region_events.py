"""Verify region-column events: focus Europe, expect Black Death banner;
focus Americas via Inca, expect plague banner; screenshot both."""
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

    def focus(stream):
        pg.evaluate("""(name) => {
          const p = [...document.querySelectorAll('path.stream')]
            .find(e => e.__data__ && e.__data__.key === name);
          p.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        }""", stream)
        pg.wait_for_timeout(1500)

    focus("Kingdom of France")
    banners = pg.evaluate(
        "() => [...document.querySelectorAll('text.event-banner')].map(t => t.textContent)")
    n = pg.evaluate("() => document.querySelectorAll('text.event-label').length")
    print("Europe banners:", banners)
    print("Europe lane events:", n)
    pg.screenshot(path="web/preview_europe_events.png", full_page=True,
                  clip={"x": 150, "y": 3950, "width": 900, "height": 800})
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)

    focus("Inca Empire")
    banners = pg.evaluate(
        "() => [...document.querySelectorAll('text.event-banner')].map(t => t.textContent)")
    print("Americas banners:", banners)
    pg.keyboard.press("Escape")
    b.close()
    print("errors:", errors if errors else "none")
