import json
import threading
import urllib.error
import urllib.request

import pytest

from ghost import places, search, server



def make_index():
    rows = [
        places.Place("1", "Madrid", "ES", 40.42, -3.70, 3300000, "Europe/Madrid"),
        places.Place("2", "Wellington", "NZ", -41.29, 174.78, 200000, "Pacific/Auckland"),
        places.Place("3", "Madison", "US", 43.07, -89.40, 270000, "America/Chicago"),
    ]
    keys = sorted((places.plain(p.name), i) for i, p in enumerate(rows))
    return rows, keys


IDEA = {"title": "Run strides", "area": "Health", "summary": "Runners add short fast strides.", "benefits": ["Faster turnover"],
        "source_url": "https://example.org/a"}


def fake_search(prompt):
    if "FAIL" in prompt:
        raise search.SearchError("Claude Code is not logged in.")
    if "PROSE" in prompt:
        return "Here you go:\n" + json.dumps([IDEA]) + "\nGood luck!"
    if "BADJSON" in prompt:
        return "nothing useful"
    return json.dumps([IDEA])


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    web = tmp_path_factory.mktemp("web")
    (web / "index.html").write_text("<h1>Ghost</h1>", encoding="utf-8")
    httpd = server.make_server(make_index(), port=0, web=web, searcher=fake_search, imager=lambda url: "https://img.example.org/p.jpg")
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


def test_prompt(base):
    status, data = post(base + "/api/prompt", {"request": "I run 5 km", "region": "Japan", "count": 2, "tried": ["A"]})
    assert status == 200
    assert "2 different ideas" in data["prompt"]
    assert "Examples should come from: Japan." in data["prompt"]
    assert "Do not repeat these: A." in data["prompt"]


def test_prompt_needs_a_request(base):
    assert post(base + "/api/prompt", {"request": "  "})[0] == 400


def test_parse_ok(base):
    idea = {"title": "T", "summary": "S", "benefits": ["B"], "source_url": "https://example.org"}
    status, data = post(base + "/api/parse", {"text": json.dumps([idea]), "area": "Study"})
    assert status == 200
    assert data["items"][0]["area"] == "Study"


def test_parse_error(base):
    status, data = post(base + "/api/parse", {"text": "nonsense"})
    assert status == 400 and "error" in data


def test_bad_json_body(base):
    req = urllib.request.Request(base + "/api/prompt", data=b"{oops", headers={"Content-Type": "application/json"})
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


def test_status_reports_search(base):
    assert json.loads(get(base + "/api/status")[1]) == {"search": True}


def test_search_returns_ideas(base):
    status, data = post(base + "/api/search", {"prompt": "find ideas"})
    assert status == 200
    assert data["items"][0]["title"] == "Run strides"
    assert data["items"][0]["area"] == "Health"
    assert data["items"][0]["image"] == "https://img.example.org/p.jpg"


def test_search_reads_an_answer_with_text_around_it(base):
    status, data = post(base + "/api/search", {"prompt": "PROSE"})
    assert status == 200 and data["items"][0]["title"] == "Run strides"


def test_search_failure_gives_a_message(base):
    status, data = post(base + "/api/search", {"prompt": "FAIL"})
    assert status == 503 and data["error"] == "Claude Code is not logged in."


def test_search_unreadable_answer(base):
    status, data = post(base + "/api/search", {"prompt": "BADJSON"})
    assert status == 502 and "could not be read" in data["error"]


def test_search_needs_a_prompt(base):
    assert post(base + "/api/search", {"prompt": "  "})[0] == 400


def test_post_needs_a_json_content_type(base):
    req = urllib.request.Request(base + "/api/search", data=b'{"prompt":"x"}', headers={"Content-Type": "text/plain"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 415


def test_search_unavailable(tmp_path):
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert json.loads(get(url + "/api/status")[1]) == {"search": False}
        assert post(url + "/api/search", {"prompt": "x"})[0] == 503
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_failing_image_lookup_does_not_break_the_search(tmp_path):
    def broken(url):
        raise RuntimeError("no network")
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=fake_search, imager=broken)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        status, data = post(url + "/api/search", {"prompt": "x"})
        assert status == 200 and data["items"][0]["image"] == ""
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_pages_are_never_cached(base):
    with urllib.request.urlopen(base + "/") as r:
        assert r.headers["Cache-Control"] == "no-store"
