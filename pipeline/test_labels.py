from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)
    n = pg.evaluate("() => document.querySelectorAll('text.stream-label').length")
    clipped = pg.evaluate("() => [...document.querySelectorAll('text.stream-label')].every(t => t.getAttribute('clip-path'))")
    print("stream labels:", n, "| all clipped:", clipped)

    # check no label text box extends past its stream lane at the label's center.
    overflow = pg.evaluate("""() => {
      let bad = 0;
      for (const t of document.querySelectorAll('text.stream-label')) {
        const bb = t.getBBox();
        // its clip is the stream area; if clipped, visual can't overflow. Count
        // labels whose UNCLIPPED bbox is wider than 0 (sanity only).
        if (!t.getAttribute('clip-path')) bad++;
      }
      return bad;
    }""")
    print("unclipped labels:", overflow)

    # focus a region, ensure column renders + no errors, then unfocus
    pg.evaluate("""() => {
      const p=[...document.querySelectorAll('path.stream')].find(e=>e.__data__&&e.__data__.key==='Mughal Empire');
      p.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    }""")
    pg.wait_for_timeout(1400)
    cols = pg.evaluate("() => [...document.querySelectorAll('path.stream')].filter(e=>e.__data__&&String(e.__data__.key).startsWith('__col__')).length")
    coll = pg.evaluate("() => [...document.querySelectorAll('text.stream-label')].every(t => t.getAttribute('clip-path'))")
    print("focus columns:", cols, "| labels clipped in focus:", coll)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    print("unfocused ok:", pg.evaluate("() => !document.querySelector('.focus-title')"))
    b.close()
    print("errors:", errs if errs else "none")
