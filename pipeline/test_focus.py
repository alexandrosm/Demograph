"""Headless test of focus UI: region focus (click) + civ focus (shift-click)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1400})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2000)
    # Region focus: click Republic of India -> Indian subcontinent column.
    pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Republic of India');
      p.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    }""")
    pg.wait_for_timeout(1500)
    title = pg.evaluate("() => document.querySelector('.focus-title')?.textContent")
    lanes = pg.evaluate("""() => [...document.querySelectorAll('path.stream')]
      .map(e => e.__data__?.key).filter(k => k && k.startsWith('__col__'))""")
    print("region focus title:", title)
    interesting = [k for k in lanes if any(
        s in k for s in ("Mughal", "Raj", "Gupta", "Maurya", "Unrecorded", "Stateless"))]
    print("column lanes of interest:", interesting)
    print("total column lanes:", len(lanes))
    pg.screenshot(path="web/preview_region_focus.png", full_page=True)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    # Civ focus via shift-click.
    pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Qing Dynasty');
      p.dispatchEvent(new MouseEvent('click', {bubbles: true, shiftKey: true}));
    }""")
    pg.wait_for_timeout(1500)
    print("civ focus title:", pg.evaluate(
        "() => document.querySelector('.focus-title')?.textContent"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    print("restored:", pg.evaluate("() => !document.querySelector('.focus-title')"))
    b.close()
    print("errors:", errors if errors else "none")
