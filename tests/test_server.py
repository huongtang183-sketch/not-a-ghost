import json
import threading
import urllib.error
import urllib.request

import pytest

from ghost import places, server

VARIANTS = {"10": "a", "30": "b", "50": "c", "100": "d"}


def make_index():
    rows = [
        places.Place("1", "Madrid", "ES", 40.42, -3.70, 3300000, "Europe/Madrid"),
        places.Place("2", "Wellington", "NZ", -41.29, 174.78, 200000, "Pacific/Auckland"),
        places.Place("3", "Madison", "US", 43.07, -89.40, 270000, "America/Chicago"),
    ]
    keys = sorted((places.plain(p.name), i) for i, p in enumerate(rows))
    return rows, keys


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    web = tmp_path_factory.mktemp("web")
    (web / "index.html").write_text("<h1>Ghost</h1>", encoding="utf-8")
    httpd = server.make_server(make_index(), port=0, web=web)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_serves_the_web_page(base):
    status, text = get(base + "/")
    assert status == 200 and "Ghost" in text


def test_place_search(base):
    status, text = get(base + "/api/places?q=mad")
    assert status == 200
    assert [p["name"] for p in json.loads(text)] == ["Madrid", "Madison"]


def test_place_search_too_short(base):
    assert json.loads(get(base + "/api/places?q=ma")[1]) == []


def test_opposite(base):
    status, text = get(base + "/api/opposite?id=1")
    data = json.loads(text)
    assert status == 200
    assert data["place"]["name"] == "Wellington"
    assert data["gap_km"] < 200
    assert "Wellington, NZ" in data["region"]


def test_opposite_unknown_id(base):
    assert get(base + "/api/opposite?id=999")[0] == 404


def test_prompt(base):
    status, data = post(base + "/api/prompt", {"day": None, "region": "Japan", "count": 2, "kept": ["A"]})
    assert status == 200
    assert "2 different small changes" in data["prompt"]
    assert "Examples should come from: Japan." in data["prompt"]
    assert "Kept: A." in data["prompt"]


def test_parse_ok(base):
    idea = {"title": "T", "variants": VARIANTS, "source_url": "https://example.org"}
    status, data = post(base + "/api/parse", {"text": json.dumps([idea]), "area": "Study"})
    assert status == 200
    assert data["items"][0]["area"] == "Study"


def test_parse_error(base):
    status, data = post(base + "/api/parse", {"text": "nonsense"})
    assert status == 400 and "error" in data


def test_bad_json_body(base):
    req = urllib.request.Request(base + "/api/prompt", data=b"{oops")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400


def test_unknown_api_path(base):
    assert get(base + "/api/nothing")[0] == 404


def test_activities(base):
    status, data = post(base + "/api/activities", {"q": "morn", "history": [{"text": "Morning yoga", "area": "Health"}]})
    assert status == 200
    assert data[0] == {"text": "Morning yoga", "area": "Health", "source": "yours"}


def test_activities_ignores_bad_history(base):
    status, data = post(base + "/api/activities", {"q": "morn", "history": "nonsense"})
    assert status == 200 and any(d["text"] == "Morning run" for d in data)
