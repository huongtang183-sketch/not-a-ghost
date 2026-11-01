import base64
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


SEEN = {}


def fake_search(prompt, images=()):
    SEEN["images"] = list(images)
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
    httpd = server.make_server(make_index(), port=0, web=web, searcher=fake_search,
                               imager=lambda url: "https://img.example.org/p.jpg", checker=lambda url: True)
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
    assert json.loads(get(base + "/api/status")[1]) == {"search": True, "version": server.VERSION}


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
        assert json.loads(get(url + "/api/status")[1]) == {"search": False, "version": server.VERSION}
        assert post(url + "/api/search", {"prompt": "x"})[0] == 503
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_failing_image_lookup_does_not_break_the_search(tmp_path):
    def broken(url):
        raise RuntimeError("no network")
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=fake_search, imager=broken, checker=lambda url: True)
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


def test_prompt_endpoint_uses_the_mode(tmp_path):
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        import urllib.request
        payload = json.dumps({"request": "a blender", "mode": "cheaper"}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/api/prompt", data=payload,
                                     headers={"Content-Type": "application/json"})
        assert "cheaper equivalent" in json.load(urllib.request.urlopen(req))["prompt"]
    finally:
        httpd.shutdown()


def test_location_suggests_countries_and_cities_with_coordinates(base):
    status, text = get(base + "/api/location?q=mad")
    assert status == 200
    found = json.loads(text)
    city = next(r for r in found if r["kind"] == "city" and r["name"] == "Madrid")
    assert city["label"] == "Madrid, Spain" and city["coords"] == "40.42\u00b0 N, 3.70\u00b0 W"
    status, text = get(base + "/api/location?q=jap")
    assert json.loads(text) == [{"kind": "country", "name": "Japan", "label": "Japan"}]
    assert json.loads(get(base + "/api/location?q=ja")[1]) == []


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 20).decode()


def test_search_passes_valid_photos_to_the_searcher(base):
    status, data = post(base + "/api/search", {"prompt": "find", "images": [{"data": "data:image/png;base64," + PNG}]})
    assert status == 200 and SEEN["images"] == [("image/png", PNG)]


def test_search_rejects_bad_photos(base):
    assert post(base + "/api/search", {"prompt": "find", "images": [{"data": base64.b64encode(b"not an image").decode()}]})[0] == 400
    assert post(base + "/api/search", {"prompt": "find", "images": [{"data": PNG}] * 4})[0] == 400
    assert post(base + "/api/search", {"prompt": "find", "images": [{"data": "%%%"}]})[0] == 400


def test_prompt_endpoint_uses_links_photos_and_count(base):
    body = {"request": "x", "mode": "similar", "links": ["https://a.example/b"], "photos": 1, "count": 40}
    status, data = post(base + "/api/prompt", body)
    assert status == 200 and "https://a.example/b" in data["prompt"] and "I attached 1 photo" in data["prompt"]
    assert "10 different ideas" in data["prompt"]


def run_with_checker(tmp_path, checker, answer, body=None):
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=lambda p: answer, imager=lambda u: "", checker=checker)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        return post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", dict({"prompt": "x"}, **(body or {})))
    finally:
        httpd.shutdown()
        httpd.server_close()


def two_ideas():
    return json.dumps([{"title": t, "summary": "S", "benefits": ["B"], "source_url": u}
                       for t, u in (("Dead", "https://example.org/dead"), ("Alive", "https://example.org/ok"))])


def test_an_idea_with_a_dead_link_is_dropped(tmp_path):
    status, data = run_with_checker(tmp_path, lambda u: not u.endswith("dead"), two_ideas())
    assert status == 200 and [i["title"] for i in data["items"]] == ["Alive"]


def test_search_fails_when_every_link_is_dead(tmp_path):
    status, data = run_with_checker(tmp_path, lambda u: False, two_ideas())
    assert status == 502 and "Only 0 of 1" in data["error"]


def test_a_failing_link_check_keeps_the_idea(tmp_path):
    def broken(u):
        raise RuntimeError("boom")
    status, data = run_with_checker(tmp_path, broken, two_ideas(), {"count": 2})
    assert status == 200 and len(data["items"]) == 2


def test_search_asks_again_when_no_idea_has_a_source(tmp_path):
    calls = []

    def searcher(prompt):
        calls.append(prompt)
        return "[]" if len(calls) == 1 else two_ideas()
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=searcher, imager=lambda u: "", checker=lambda u: True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, data = post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", {"prompt": "x", "count": 2})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and len(data["items"]) == 2 and len(calls) == 2 and "previous answer" in calls[1]


def test_search_gives_up_after_the_follow_ups(tmp_path):
    calls = []

    def searcher(prompt):
        calls.append(prompt)
        return "[]"
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=searcher, imager=lambda u: "", checker=lambda u: True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, _ = post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", {"prompt": "x"})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 502 and len(calls) == server.ROUNDS


def test_missing_ideas_are_requested_again_without_repeats(tmp_path):
    calls = []

    def idea(title):
        return {"title": title, "summary": "S", "benefits": ["B"], "source_url": "https://example.org/" + title}

    def searcher(prompt):
        calls.append(prompt)
        return json.dumps([idea("A")] if len(calls) == 1 else [idea("A"), idea("B")])
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=searcher, imager=lambda u: "", checker=lambda u: True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, data = post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", {"prompt": "x", "count": 2})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and [i["title"] for i in data["items"]] == ["A", "B"]
    assert "1 more idea" in calls[1] and "different from: A" in calls[1]


def test_never_more_ideas_than_requested(tmp_path):
    status, data = run_with_checker(tmp_path, lambda u: True, two_ideas(), {"count": 1})
    assert status == 200 and len(data["items"]) == 1


def test_first_request_asks_for_spare_candidates(tmp_path):
    calls = []

    def searcher(prompt):
        calls.append(prompt)
        return two_ideas()
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=searcher, imager=lambda u: "", checker=lambda u: True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", {"prompt": "x", "count": 2})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "4 candidate ideas in the array instead of 2" in calls[0]


def test_keeps_asking_until_the_requested_number_has_a_working_source(tmp_path):
    calls = []

    def searcher(prompt):
        calls.append(prompt)
        return json.dumps([{"title": f"T{len(calls)}", "summary": "S", "benefits": ["B"], "source_url": f"https://example.org/{len(calls)}"}])
    httpd = server.make_server(make_index(), port=0, web=tmp_path, searcher=searcher, imager=lambda u: "", checker=lambda u: True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, data = post(f"http://127.0.0.1:{httpd.server_address[1]}/api/search", {"prompt": "x", "count": 4})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and len(data["items"]) == 4 and len(calls) == 4


def test_no_partial_answer_when_too_few_ideas_have_a_source(tmp_path):
    status, data = run_with_checker(tmp_path, lambda u: u.endswith("ok"), two_ideas(), {"count": 2})
    assert status == 502 and "Only 1 of 2" in data["error"]
