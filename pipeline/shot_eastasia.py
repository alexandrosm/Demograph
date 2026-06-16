"""Screenshot the East Asia focus column, modern era."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 1400})
    pg.goto(url)
    pg.wait_for_timeout(2000)
    pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Qing Dynasty');
      p.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    }""")
    pg.wait_for_timeout(1500)
    print("title:", pg.evaluate(
        "() => document.querySelector('.focus-title')?.textContent"))
    lanes = pg.evaluate("""() => [...document.querySelectorAll('path.stream')]
      .map(e => e.__data__?.name).filter(n => n && n.includes('(in '))""")
    print("annotated lanes:", lanes)
    pg.screenshot(path="web/preview_eastasia_modern.png", full_page=True,
                  clip={"x": 150, "y": 4750, "width": 900, "height": 560})
    b.close()
