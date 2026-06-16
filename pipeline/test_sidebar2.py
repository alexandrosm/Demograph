from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1050})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)
    print("default scheme value:", pg.evaluate("() => document.getElementById('scheme').value"))
    print("body bg (strata sandstone ~234,217,189):",
          pg.evaluate("() => getComputedStyle(document.body).backgroundColor"))
    print("share active by default:",
          pg.evaluate("() => document.getElementById('mode-share').classList.contains('active')"))
    print("legend swatches:", pg.evaluate("() => document.querySelectorAll('.sb-legend .sw').length"))

    pg.click("#sidebar-toggle")
    pg.wait_for_timeout(400)
    # segmented toggle: switch to Absolute
    pg.evaluate("() => document.getElementById('mode-abs').click()")
    pg.wait_for_timeout(500)
    print("abs active after click:",
          pg.evaluate("() => document.getElementById('mode-abs').classList.contains('active')"),
          "| share inactive:",
          not pg.evaluate("() => document.getElementById('mode-share').classList.contains('active')"))
    # time compressed
    pg.evaluate("() => document.getElementById('time-log').click()")
    pg.wait_for_timeout(800)
    print("compressed active:", pg.evaluate("() => document.getElementById('time-log').classList.contains('active')"))
    # nav minimap toggle off
    pg.evaluate("() => document.getElementById('navmap-ck').click()")
    pg.wait_for_timeout(300)
    print("navmap hidden after toggle:",
          pg.evaluate("() => getComputedStyle(document.getElementById('navmap')).display") == "none")
    pg.evaluate("() => document.getElementById('navmap-ck').click()")  # back on
    pg.wait_for_timeout(200)
    pg.screenshot(path="web/preview_sidebar2.png", clip={"x": 0, "y": 0, "width": 280, "height": 700})
    b.close()
    print("errors:", errs if errs else "none")
