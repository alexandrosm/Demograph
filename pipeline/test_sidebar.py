from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2000)
    print("toggle text:", pg.evaluate("() => document.getElementById('sidebar-toggle').textContent.trim()"))
    print("open by default:", pg.evaluate("() => document.body.classList.contains('sb-open')"))
    print("scheme options:", pg.evaluate("() => document.getElementById('scheme').options.length"))
    # open the sidebar
    pg.click("#sidebar-toggle")
    pg.wait_for_timeout(400)
    print("after click open:", pg.evaluate("() => document.body.classList.contains('sb-open')"),
          "| toggle:", pg.evaluate("() => document.getElementById('sidebar-toggle').textContent.trim()"))
    # exercise a control: switch palette to night, toggle a mode
    pg.select_option("#scheme", "night")
    pg.wait_for_timeout(300)
    pg.click("#mode-abs")
    pg.wait_for_timeout(400)
    print("mode-abs active:", pg.evaluate("() => document.getElementById('mode-abs').classList.contains('active')"))
    print("bg after night:", pg.evaluate("() => getComputedStyle(document.body).backgroundColor"))
    pg.screenshot(path="web/preview_sidebar.png", clip={"x": 0, "y": 0, "width": 420, "height": 480})
    # close again
    pg.click("#sidebar-toggle")
    pg.wait_for_timeout(300)
    print("closed:", not pg.evaluate("() => document.body.classList.contains('sb-open')"))
    b.close()
    print("errors:", errs if errs else "none")
