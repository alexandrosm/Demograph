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

    print("labels all clipped:",
          pg.evaluate("() => [...document.querySelectorAll('text.stream-label')].every(t=>t.getAttribute('clip-path'))"))
    print("clipPath defs (world):", pg.evaluate("() => document.querySelectorAll('clipPath').length"))

    def colkeys():
        return pg.evaluate("""() => [...document.querySelectorAll('path.stream')]
          .filter(e=>e.__data__&&String(e.__data__.key).startsWith('__col__'))
          .map(e=>e.__data__.key.replace('__col__',''))""")

    # CIV focus via shift-click on a mid-stack family (sinic), check gap
    pg.evaluate("""() => {
      const p=[...document.querySelectorAll('path.stream')].find(e=>e.__data__&&e.__data__.key==='Qing Dynasty');
      p.dispatchEvent(new MouseEvent('click',{bubbles:true,shiftKey:true}));
    }""")
    pg.wait_for_timeout(1400)
    print("civ focus title:", pg.evaluate("() => document.querySelector('.focus-title')?.textContent"))
    # measure gap: column is centered; find nearest non-column stream edges to the column
    gap = pg.evaluate("""() => {
      const W=1000, colFrac=0.56, ML=84, MR=60;
      const colW=colFrac*(W-ML-MR), colX0=(W-colW)/2, colX1=colX0+colW;
      let leftMaxRight=-1, rightMinLeft=1e9;
      for(const e of document.querySelectorAll('path.stream')){
        const d=e.__data__; if(!d||String(d.key).startsWith('__col__'))continue;
        const bb=e.getBBox(); if(bb.width<0.5)continue;
        if(bb.x+bb.width<=colX0+1) leftMaxRight=Math.max(leftMaxRight,bb.x+bb.width);
        if(bb.x>=colX1-1) rightMinLeft=Math.min(rightMinLeft,bb.x);
      }
      return {colX0:Math.round(colX0), colX1:Math.round(colX1),
              leftGap:Math.round(colX0-leftMaxRight), rightGap:Math.round(rightMinLeft-colX1)};
    }""")
    print("civ parting gaps (px, want small ~16):", gap)
    pg.screenshot(path="web/preview_civfocus.png", full_page=True, clip={"x":0,"y":1700,"width":1000,"height":700})

    # rapid toggle race: Esc immediately, well within the 920ms annotate delay
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(120)
    pg.keyboard.press("Escape")  # no-op
    pg.wait_for_timeout(1500)
    print("after rapid unfocus -> focus-title gone:",
          pg.evaluate("() => !document.querySelector('.focus-title')"))
    print("world labels present:",
          pg.evaluate("() => document.querySelectorAll('text.stream-label').length") > 10)
    print("errors:", errs if errs else "none")
    b.close()
