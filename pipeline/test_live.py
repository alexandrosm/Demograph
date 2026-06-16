"""Verify the deployed site: minimap loads + syncs, exports work."""
from playwright.sync_api import sync_playwright

URL = "https://alexandrosm.github.io/Demograph/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1700, "height": 1200})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(2500)
    print("typeof MINIMAP:", pg.evaluate("() => typeof MINIMAP"))
    print("land polys:", pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-land').length"))
    print("polities @default:", pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-pol').length"))
    print("default cap:", pg.evaluate("() => document.getElementById('mm-cap').textContent"))
    # hover the Mongol Empire stream
    ok = pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Mongol Empire');
      if (!p) return false;
      const r = p.getBoundingClientRect();
      p.dispatchEvent(new MouseEvent('mousemove', {bubbles:true,
        clientX:r.left+Math.min(20,r.width/2), clientY:r.top+r.height/2}));
      return true;
    }""")
    pg.wait_for_timeout(400)
    print("hover dispatched:", ok, "| cap after:",
          pg.evaluate("() => document.getElementById('mm-cap').textContent"),
          "| polities:", pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-pol').length"))
    pg.screenshot(path="web/preview_minimap.png",
                  clip={"x": 1396, "y": 88, "width": 304, "height": 210})
    # exports
    with pg.expect_download() as d1:
        pg.click("#export-svg")
    print("SVG:", d1.value.suggested_filename)
    with pg.expect_download() as d2:
        pg.click("#export-png")
    print("PNG:", d2.value.suggested_filename)
    b.close()
    print("errors:", errs if errs else "none")
