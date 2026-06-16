"""Debug tooltips in focus mode: what element does a real pointer hit, and
does the tip render?"""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2000)
    pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Republic of India');
      p.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    }""")
    pg.wait_for_timeout(1600)
    # scroll the column's mid-history into view, then probe the real pointer
    pg.evaluate("window.scrollTo(0, 3000)")
    pg.wait_for_timeout(300)
    probe = pg.evaluate("""() => {
      const el = document.elementFromPoint(600, 450);
      return {tag: el?.tagName, cls: el?.getAttribute('class'),
              key: el?.__data__?.key ?? null};
    }""")
    print("elementFromPoint(600,450):", probe)
    pg.mouse.move(600, 450)
    pg.wait_for_timeout(300)
    tip = pg.evaluate("""() => {
      const t = document.getElementById('tip');
      return {display: t.style.display, html: t.innerHTML.slice(0, 120)};
    }""")
    print("tip after real mouse.move:", tip)
    # also probe a SIDE stream (left of column)
    probe2 = pg.evaluate("""() => {
      const el = document.elementFromPoint(150, 450);
      return {tag: el?.tagName, key: el?.__data__?.key ?? null};
    }""")
    pg.mouse.move(150, 450)
    pg.wait_for_timeout(300)
    tip2 = pg.evaluate("""() => {
      const t = document.getElementById('tip');
      return {display: t.style.display, html: t.innerHTML.slice(0, 120)};
    }""")
    print("side probe:", probe2)
    print("side tip:", tip2)
    b.close()
    print("errors:", errors if errors else "none")
