"""Draw the app icon (the ghost inside an eight-pointed star) as SVG and PNG (192 and 512 px) into docs/icons.

    python -m tools.make_icons

The PNG step needs Playwright (pip install playwright). The SVG is written either way.
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
GHOST = (
    '<path d="M18 98V46C18 22 36 8 60 8s42 14 42 38v52l-13-11-14 13-15-13-15 13-14-13z" '
    'fill="#fff" stroke="#16143f" stroke-width="5" stroke-linejoin="round"/>'
    '<circle cx="45" cy="48" r="6" fill="#16143f"/><circle cx="75" cy="48" r="6" fill="#16143f"/>'
    '<ellipse cx="36" cy="62" rx="7" ry="4" fill="#ff6b8b"/><ellipse cx="84" cy="62" rx="7" ry="4" fill="#ff6b8b"/>'
    '<path d="M52 64q8 7 16 0" stroke="#16143f" stroke-width="4" fill="none" stroke-linecap="round"/>'
)


def square(radius, turn):
    """Corner points of a square with the given circumradius, turned by `turn` degrees."""
    corners = [(radius * math.cos(math.radians(turn + 90 * i)), radius * math.sin(math.radians(turn + 90 * i))) for i in range(4)]
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in corners)


# The ghost sits in the middle of an eight-pointed star made of two squares, one turned 45 degrees.
# Everything is drawn inside the middle 70% of the tile, so a phone can round or crop the corners.
STAR = (
    f'<polygon points="{square(60, 45)}" fill="#3a3aff" stroke="#16143f" stroke-width="3.5" stroke-linejoin="round"/>'
    f'<polygon points="{square(60, 0)}" fill="#3a3aff" stroke="#16143f" stroke-width="3.5" stroke-linejoin="round"/>'
    '<circle r="42" fill="#d6e2ff" stroke="#16143f" stroke-width="3"/>'
    f'<g transform="translate(-30 -29) scale(.5)">{GHOST}</g>'
)
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-100 -100 200 200"><rect x="-100" y="-100" width="200" height="200" fill="#d6e2ff"/>'
    f'<g transform="scale(1.1)">{STAR}</g></svg>'
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
