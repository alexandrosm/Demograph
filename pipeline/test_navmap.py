from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)
    print("navmap streams cloned:", pg.evaluate("() => document.querySelectorAll('#navmap-svg path.stream').length"))
    v0 = pg.evaluate("() => ({top: document.getElementById('navmap-view').style.top, h: document.getElementById('navmap-view').style.height})")
    print("view rect @ top:", v0)
    # scroll down halfway and check the view rect moved
    pg.evaluate("() => window.scrollTo(0, 2500)")
    pg.wait_for_timeout(300)
    v1 = pg.evaluate("() => document.getElementById('navmap-view').style.top")
    print("view top after scroll 2500:", v1)
    # click near bottom of navmap -> should scroll near bottom of chart
    pg.evaluate("""() => {
      const r = document.getElementById('navmap').getBoundingClientRect();
      document.getElementById('navmap').dispatchEvent(new MouseEvent('mousedown',
        {bubbles:true, clientX:r.left+10, clientY:r.top+r.height*0.85}));
    }""")
    pg.wait_for_timeout(300)
    print("scrollY after click@0.85:", pg.evaluate("() => Math.round(window.scrollY)"),
          "of max", pg.evaluate("() => Math.round(document.body.scrollHeight - window.innerHeight)"))
    pg.evaluate("() => window.scrollTo(0, 1400)")
    pg.wait_for_timeout(300)
    pg.screenshot(path="web/preview_navmap.png", clip={"x": 1384, "y": 0, "width": 116, "height": 900})
    b.close()
    print("errors:", errs if errs else "none")
