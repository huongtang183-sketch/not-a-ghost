import json

import pytest

from ghost import coach
from tools import build_demo


@pytest.fixture(scope="module")
def ideas():
    return json.loads(build_demo.IDEAS.read_text(encoding="utf-8"))


def test_every_sample_idea_is_valid_and_sourced(ideas):
    kept = coach.parse_answer(json.dumps(ideas))
    assert len(kept) == len(ideas)
    assert all(i["source_url"].startswith("https://") and i["source_title"] for i in kept)


def test_every_mode_has_a_sample_idea(ideas):
    assert {i["mode"] for i in ideas} == set(coach.MODES)


def test_build_writes_the_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(build_demo, "OUT", tmp_path)
    build_demo.build()
    for name in build_demo.PAGES:
        page = (tmp_path / name).read_text(encoding="utf-8")
        assert "window.GHOST_DEMO" in page and 'rel="manifest"' in page and "serviceWorker" in page
    manifest = json.loads((tmp_path / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone" and manifest["start_url"] == "./"
    assert "ghost-demo" in (tmp_path / "sw.js").read_text(encoding="utf-8")


def test_the_live_pages_have_no_demo_switch():
    for name in build_demo.PAGES:
        assert "window.GHOST_DEMO = {" not in (build_demo.WEB / name).read_text(encoding="utf-8")
