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

from ghost import activities, coach, geo, places

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 1_000_000


def place_json(p):
    return {"id": p.id, "name": p.name, "country": p.country, "lat": p.lat, "lng": p.lng, "timezone": p.timezone}


class Handler(SimpleHTTPRequestHandler):
    index = None  # (places, keys), set by make_server
    by_id = None

    def log_message(self, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/api/places":
            found = places.search(self.index, query.get("q", [""])[0])
            return self.send_json([place_json(p) for p in found])
        if url.path == "/api/opposite":
            here = self.by_id.get(query.get("id", [""])[0])
            if here is None:
                return self.send_json({"error": "Unknown place."}, 404)
            there, gap = geo.opposite(self.index, here)
            return self.send_json({
                "place": place_json(there),
                "gap_km": round(gap),
                "distance_km": round(geo.distance_km(here.lat, here.lng, there.lat, there.lng)),
                "region": coach.region_hint(self.index, here),
            })
        if url.path.startswith("/api/"):
            return self.send_json({"error": "Not found."}, 404)
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            size = int(self.headers.get("Content-Length", 0))
            if size > MAX_BODY:
                return self.send_json({"error": "Request too large."}, 413)
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Body must be a JSON object.")
        except ValueError as error:
            return self.send_json({"error": str(error) or "Invalid JSON."}, 400)
        if path == "/api/activities":
            history = body.get("history", [])
            history = [h for h in history if isinstance(h, dict)] if isinstance(history, list) else []
            return self.send_json(activities.suggest(str(body.get("q", "")), history))
        if path == "/api/prompt":
            prompt = coach.build_prompt(
                body.get("day"), body.get("region", ""), body.get("limit", ""), int(body.get("count") or 1),
                body.get("kept", []), body.get("dropped", []), body.get("tried", []))
            return self.send_json({"prompt": prompt})
        if path == "/api/parse":
            try:
                items = coach.parse_answer(str(body.get("text", "")), body.get("area") or "Other")
            except ValueError as error:
                return self.send_json({"error": str(error)}, 400)
            return self.send_json({"items": items})
        self.send_json({"error": "Not found."}, 404)


def make_server(index, port=8000, web=WEB):
    handler = type("GhostHandler", (Handler,), {"index": index, "by_id": {p.id: p for p in index[0]}})
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
