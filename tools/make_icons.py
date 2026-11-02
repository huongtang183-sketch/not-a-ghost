"""Draw the ghost icon as SVG and PNG (192 and 512 px) into docs/icons.

    python -m tools.make_icons

The PNG step needs Playwright (pip install playwright). The SVG is written either way.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
GHOST = (
    '<path d="M18 98V46C18 22 36 8 60 8s42 14 42 38v52l-13-11-14 13-15-13-15 13-14-13z" '
    'fill="#fff" stroke="#16143f" stroke-width="5" stroke-linejoin="round"/>'
    '<circle cx="45" cy="48" r="6" fill="#16143f"/><circle cx="75" cy="48" r="6" fill="#16143f"/>'
    '<ellipse cx="36" cy="62" rx="7" ry="4" fill="#ff6b8b"/><ellipse cx="84" cy="62" rx="7" ry="4" fill="#ff6b8b"/>'
    '<path d="M52 64q8 7 16 0" stroke="#16143f" stroke-width="4" fill="none" stroke-linecap="round"/>'
)
# the ghost sits inside the middle 60% of the tile, so a phone can round or crop the corners
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" fill="#d6e2ff"/>'
    f'<g transform="translate(24 24) scale(.6)">{GHOST}</g></svg>'
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(SVG, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size in (192, 512):
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(f'<body style="margin:0">{SVG.replace("<svg ", f"<svg width={size} height={size} ")}</body>')
            page.screenshot(path=str(OUT / f"icon-{size}.png"))
        browser.close()


if __name__ == "__main__":
    main()
