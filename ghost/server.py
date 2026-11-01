"""Local server: serves the web app and answers its questions with the Python code.

Run:
    python -m ghost.server
then open http://127.0.0.1:8000
"""
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from concurrent.futures import ThreadPoolExecutor

import base64
import binascii

from ghost import activities, coach, countries, linkcheck, places, preview, search

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 1_000_000
MAX_BODY_PHOTOS = 8_000_000
MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 2_500_000
PHOTO_TYPES = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"GIF8", "image/gif"))


def place_json(p):
    return {"id": p.id, "name": p.name, "country": p.country, "lat": p.lat, "lng": p.lng, "timezone": p.timezone}


def clean_photos(raw):
    """Check the photos sent by the page. Returns [(media type, base64 text)] or raises ValueError."""
    if not isinstance(raw, list):
        return []
    if len(raw) > MAX_PHOTOS:
        raise ValueError(f"At most {MAX_PHOTOS} photos.")
    out = []
    for item in raw:
        text = str(item.get("data", "") if isinstance(item, dict) else "")
        text = text.split(",", 1)[1] if text.startswith("data:") and "," in text else text
        try:
            blob = base64.b64decode(text, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("A photo could not be read.") from None
        if len(blob) > MAX_PHOTO_BYTES:
            raise ValueError("A photo is too large.")
        kind = next((k for magic, k in PHOTO_TYPES if blob.startswith(magic)), "")
        if not kind and blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
            kind = "image/webp"
        if not kind:
            raise ValueError("Photos must be JPEG, PNG, GIF or WebP.")
        out.append((kind, base64.b64encode(blob).decode()))
    return out


def format_coord(value, plus, minus):
    return f"{abs(value):.2f}\u00b0 {plus if value >= 0 else minus}"


class Handler(SimpleHTTPRequestHandler):
    index = None  # (places, keys), set by make_server
    searcher = None  # function(prompt) -> text, or None when search is not available
    imager = staticmethod(lambda url: "")  # function(url) -> preview image address
    checker = staticmethod(lambda url: True)  # function(url) -> False if the link is clearly dead

    def log_message(self, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # always show the newest page after an update
        super().end_headers()

    def safe_alive(self, url):
        try:
            return bool(self.checker(url))
        except Exception:
            return True

    def safe_image(self, url):
        try:
            return self.imager(url) if url else ""
        except Exception:
            return ""

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/api/places":
            found = places.search(self.index, query.get("q", [""])[0])
            return self.send_json([place_json(p) for p in found])
        if url.path == "/api/location":
            q = query.get("q", [""])[0]
            out = [dict(r, label=r["name"]) for r in countries.search(q)]
            for p in places.search(self.index, q, 6):
                country = countries.country_name(p.country)
                out.append({"kind": "city", "name": p.name, "country": country, "lat": p.lat, "lng": p.lng,
                            "label": f"{p.name}, {country}", "coords": f"{format_coord(p.lat, 'N', 'S')}, {format_coord(p.lng, 'E', 'W')}"})
            return self.send_json(out)
        if url.path == "/api/status":
            return self.send_json({"search": self.searcher is not None})
        if url.path.startswith("/api/"):
            return self.send_json({"error": "Not found."}, 404)
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self.send_json({"error": "Content-Type must be application/json."}, 415)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if size > (MAX_BODY_PHOTOS if path == "/api/search" else MAX_BODY):
                return self.send_json({"error": "Request too large."}, 413)
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Body must be a JSON object.")
        except ValueError as error:
            return self.send_json({"error": str(error) or "Invalid JSON."}, 400)
        if path == "/api/search":
            if self.searcher is None:
                return self.send_json({"error": "Search is not available."}, 503)
            prompt = str(body.get("prompt", "")).strip()
            if not prompt:
                return self.send_json({"error": "Empty request."}, 400)
            try:
                photos = clean_photos(body.get("images"))
            except ValueError as error:
                return self.send_json({"error": str(error)}, 400)
            try:
                answer = self.searcher(prompt, images=photos) if photos else self.searcher(prompt)
                items = coach.parse_answer(answer, str(body.get("area") or "Other"))
            except search.SearchError as error:
                return self.send_json({"error": str(error)}, 503)
            except ValueError as error:
                return self.send_json({"error": "Claude's answer could not be read. " + str(error)}, 502)
            with ThreadPoolExecutor(max_workers=4) as pool:
                alive = list(pool.map(self.safe_alive, [i["source_url"] for i in items]))
            items = [i for i, ok in zip(items, alive, strict=True) if ok]  # a clearly dead link is dropped
            if not items:
                return self.send_json({"error": "None of the source links opened. Try again."}, 502)
            with ThreadPoolExecutor(max_workers=4) as pool:
                images = list(pool.map(self.safe_image, [i["source_url"] for i in items]))
            for item, image in zip(items, images, strict=True):
                item["image"] = image
            return self.send_json({"items": items})
        if path == "/api/activities":
            history = body.get("history", [])
            history = [h for h in history if isinstance(h, dict)] if isinstance(history, list) else []
            return self.send_json(activities.suggest(str(body.get("q", "")), history))
        if path == "/api/prompt":
            request = str(body.get("request", "")).strip()
            if not request:
                return self.send_json({"error": "Empty request."}, 400)
            links = body.get("links")
            tried = body.get("tried", [])
            prompt = coach.build_prompt(
                request,
                region=str(body.get("region", "")),
                limit=str(body.get("limit", "")),
                count=max(1, min(int(body.get("count") or 1), coach.MAX_IDEAS)),
                keep_same=str(body.get("keep_same", "")),
                tried=[str(t) for t in tried if isinstance(t, str)],
                mode=str(body.get("mode", "improve")),
                links=[str(x) for x in links if isinstance(x, str)] if isinstance(links, list) else [],
                photos=max(0, min(int(body.get("photos") or 0), MAX_PHOTOS)),
            )
            return self.send_json({"prompt": prompt})
        if path == "/api/parse":
            try:
                items = coach.parse_answer(str(body.get("text", "")), body.get("area") or "Other")
            except ValueError as error:
                return self.send_json({"error": str(error)}, 400)
            return self.send_json({"items": items})
        self.send_json({"error": "Not found."}, 404)


def make_server(index, port=8000, web=WEB, searcher="auto", imager=preview.find_image, checker=linkcheck.is_alive):
    if searcher == "auto":
        searcher = search.run_claude if search.find_claude() else None
    handler = type("GhostHandler", (Handler,), {"index": index,
                                                "searcher": staticmethod(searcher) if searcher else None,
                                                "imager": staticmethod(imager), "checker": staticmethod(checker)})
    return ThreadingHTTPServer(("127.0.0.1", port), partial(handler, directory=str(web)))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    server = make_server(places.load())
    print("Ghost is running at http://127.0.0.1:8000  (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
