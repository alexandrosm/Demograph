"""Headless test: minimap renders + syncs to hover, and SVG/PNG export work."""
from pathlib import Path

from playwright.sync_api import sync_playwright

url = (Path("web") / "index.html").resolve().as_uri()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1700, "height": 1200})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(2500)

    land = pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-land').length")
    pol0 = pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-pol').length")
    cap0 = pg.evaluate("() => document.getElementById('mm-cap').textContent")
    print(f"minimap: {land} land polys, {pol0} polities @ default, cap='{cap0}'")

    # Hover a stream -> minimap should update year + highlight.
    pg.evaluate("""() => {
      const p = [...document.querySelectorAll('path.stream')]
        .find(e => e.__data__ && e.__data__.key === 'Mongol Empire');
      const r = p.getBoundingClientRect();
      p.dispatchEvent(new MouseEvent('mousemove', {bubbles:true,
        clientX:r.left+r.width/2, clientY:r.top+r.height/2}));
    }""")
    pg.wait_for_timeout(400)
    cap1 = pg.evaluate("() => document.getElementById('mm-cap').textContent")
    pol1 = pg.evaluate("() => document.querySelectorAll('#minimap-svg .mm-pol').length")
    print(f"after hover Mongol: cap='{cap1}', {pol1} polities")

    # SVG export
    with pg.expect_download() as dl_info:
        pg.click("#export-svg")
    dl = dl_info.value
    svg_path = Path("web") / "_test_export.svg"
    dl.save_as(svg_path)
    svg_txt = svg_path.read_text(encoding="utf-8")[:300]
    print(f"SVG export: {dl.suggested_filename}, {svg_path.stat().st_size//1024} KB, "
          f"starts ok={svg_txt.lstrip().startswith('<svg')}")

    # PNG export
    with pg.expect_download() as dl2_info:
        pg.click("#export-png")
    dl2 = dl2_info.value
    png_path = Path("web") / "_test_export.png"
    dl2.save_as(png_path)
    print(f"PNG export: {dl2.suggested_filename}, {png_path.stat().st_size//1024} KB")

    # screenshot the minimap region
    pg.screenshot(path="web/preview_minimap.png",
                  clip={"x": 1400, "y": 90, "width": 300, "height": 200})
    b.close()
    svg_path.unlink(missing_ok=True)
    png_path.unlink(missing_ok=True)
    print("errors:", errors if errors else "none")
