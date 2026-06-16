from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2200)

    def tick_y(year_label):
        return pg.evaluate("""(lbl) => {
          const t = [...document.querySelectorAll('.year-tick-l')].find(e => e.textContent === lbl);
          return t ? +t.getAttribute('y') : null;
        }""", year_label)

    print("world map hidden by default:",
          pg.evaluate("() => getComputedStyle(document.getElementById('minimap')).display") == "none")
    print("time-linear active:",
          pg.evaluate("() => document.getElementById('time-linear').classList.contains('active')"))
    lin = {y: tick_y(y) for y in ["1000 BCE", "1 CE", "1500 CE", "2000 CE"]}
    print("linear tick y:", lin)

    pg.evaluate("() => document.getElementById('time-log').click()")
    pg.wait_for_timeout(1300)
    log = {y: tick_y(y) for y in ["1000 BCE", "1 CE", "1500 CE", "2000 CE"]}
    print("log tick y:", log)
    # In log mode recent gap (1500->2000) should be LARGER than deep-past gap of similar span
    print("log expands recent: gap(1500..2000)=%.0f vs gap(1000BCE..1CE)=%.0f"
          % (log["2000 CE"] - log["1500 CE"], log["1 CE"] - log["1000 BCE"]))

    pg.evaluate("() => document.getElementById('worldmap-ck').click()")
    pg.wait_for_timeout(500)
    print("world map shown after toggle:",
          pg.evaluate("() => getComputedStyle(document.getElementById('minimap')).display"))

    pg.screenshot(path="web/preview_logtime.png", full_page=True)
    b.close()
    print("errors:", errs if errs else "none")
