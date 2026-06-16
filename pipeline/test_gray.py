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
    print("old #nogray gone:", pg.evaluate("() => !document.getElementById('nogray')"))
    print("gray-show active default:",
          pg.evaluate("() => document.getElementById('gray-show').classList.contains('active')"))
    # residual stream visible at 1500 (gray) before hiding
    res_before = pg.evaluate("""() => {
      const e=[...document.querySelectorAll('path.stream')].find(x=>x.__data__&&x.__data__.key==='__statelessL');
      return e ? Math.round(e.getBBox().width) : -1;
    }""")
    print("stateless-left band width (shown):", res_before)
    pg.evaluate("() => document.getElementById('gray-hide').click()")
    pg.wait_for_timeout(1300)
    print("gray-hide active after click:",
          pg.evaluate("() => document.getElementById('gray-hide').classList.contains('active')"),
          "| show inactive:",
          not pg.evaluate("() => document.getElementById('gray-show').classList.contains('active')"))
    res_after = pg.evaluate("""() => {
      const e=[...document.querySelectorAll('path.stream')].find(x=>x.__data__&&x.__data__.key==='__statelessL');
      return e ? Math.round(e.getBBox().width) : -1;
    }""")
    print("stateless band after hide (want -1, gone):", res_after)
    pg.evaluate("() => document.getElementById('gray-show').click()")
    pg.wait_for_timeout(1000)
    print("restored to shown:",
          pg.evaluate("() => document.getElementById('gray-show').classList.contains('active')"))
    b.close()
    print("errors:", errs if errs else "none")
