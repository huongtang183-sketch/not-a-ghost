"""Build the static demo that GitHub Pages publishes from the docs folder.

    python -m tools.build_demo

The demo is the same two pages as web/, with sample ideas instead of live search,
plus what a phone needs to install it (manifest, icons, service worker).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = ROOT / "docs"
IDEAS = Path(__file__).resolve().parent / "demo_ideas.json"
CACHE = "ghost-demo-v1"
DESCRIPTION = "Sourced ideas to change one small thing, and a view of what your life is juggling."
PAGES = ["index.html", "pattern.html"]
ICONS = [192, 512]

HEAD = (
    '<link rel="manifest" href="manifest.webmanifest">\n'
    '<meta name="theme-color" content="#d6e2ff">\n'
    '<link rel="icon" href="icons/icon.svg" type="image/svg+xml">\n'
    '<link rel="apple-touch-icon" href="icons/icon-192.png">\n'
    "<script>window.GHOST_DEMO = {data};</script>\n"
)
REGISTER = "<script>if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});</script>\n"

MANIFEST = {
    "name": "Ghost",
    "short_name": "Ghost",
    "description": DESCRIPTION,
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#d6e2ff",
    "theme_color": "#d6e2ff",
    "icons": [
        {"src": f"icons/icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any maskable"} for n in ICONS
    ],
}

SERVICE_WORKER = """const CACHE = '%(cache)s';
const FILES = %(files)s;
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && new URL(e.request.url).origin === location.origin) {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy));
    }
    return r;
  }).catch(() => caches.match(e.request).then(hit => hit || caches.match('index.html'))));
});
"""


def demo_page(html, ideas):
    """The page with the demo switch, the manifest links and the service worker added."""
    head = HEAD.replace("{data}", json.dumps({"ideas": ideas}, ensure_ascii=False))
    html = re.sub(r"</title>", "</title>\n" + head, html, count=1)
    return html.replace("</body>", REGISTER + "</body>", 1)


def build():
    ideas = json.loads(IDEAS.read_text(encoding="utf-8"))
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    for name in PAGES:
        (OUT / name).write_text(demo_page((WEB / name).read_text(encoding="utf-8"), ideas), encoding="utf-8")
    (OUT / "manifest.webmanifest").write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    files = ["./", *PAGES, "manifest.webmanifest", "icons/icon.svg", *[f"icons/icon-{n}.png" for n in ICONS]]
    (OUT / "sw.js").write_text(SERVICE_WORKER % {"cache": CACHE, "files": json.dumps(files)}, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    return [OUT / n for n in [*PAGES, "manifest.webmanifest", "sw.js"]]


if __name__ == "__main__":
    for path in build():
        print("wrote", path.relative_to(ROOT))
    print("Icons are in docs/icons (see tools/make_icons.py to regenerate them).")
