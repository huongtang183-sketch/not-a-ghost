import json

import pytest

from ghost import coach

VARIANTS = {"10": "a", "30": "b", "50": "c", "100": "d"}


def idea(**changes):
    base = {"title": "Redo from a blank page", "why": "w", "source_type": "research", "from": "Japan",
            "source_title": "A study", "source_url": "https://example.org/x", "variants": dict(VARIANTS)}
    base.update(changes)
    return base


def test_prompt_contains_the_day_and_the_rules():
    day = {"area": "Study", "text": "Rereading notes", "minutes": 90, "solved": 6, "sleep": 7, "feel": 3}
    p = coach.build_prompt(day)
    assert "Rereading notes (area: Study), 90 minutes, 6 items finished, slept 7 hours, felt 3 out of 5." in p
    assert "Use only sources you opened" in p
    assert "Never suggest cutting sleep" in p
    assert "10%, 30%, 50% and 100%" in p
    assert "Reply with a JSON array only" in p


def test_prompt_defaults_and_limit():
    p = coach.build_prompt(None)
    assert "Examples should come from: anywhere in the world." in p
    assert "I have not logged a day yet" in p
    assert "My limit" not in p
    assert "My limit: under 10 CHF." in coach.build_prompt(None, limit="under 10 CHF")


def test_prompt_count():
    assert "ONE small change" in coach.build_prompt(None, count=1)
    assert "3 different small changes" in coach.build_prompt(None, count=3)


def test_prompt_lists_history():
    p = coach.build_prompt(None, kept=["A"], dropped=["B", "C"], tried=["D"])
    assert "Kept: A. Dropped: B; C. Already tried: D." in p
    assert "Kept: none. Dropped: none. Already tried: none." in coach.build_prompt(None)


def test_parse_valid_list():
    items = coach.parse_answer(json.dumps([idea()]), "Study")
    assert items[0]["title"] == "Redo from a blank page"
    assert items[0]["area"] == "Study"
    assert items[0]["source_type"] == "research"
    assert items[0]["variants"] == VARIANTS


def test_parse_accepts_code_fence_and_single_object():
    text = "```json\n" + json.dumps(idea()) + "\n```"
    assert len(coach.parse_answer(text)) == 1


def test_parse_drops_incomplete_ideas():
    bad_sizes = idea(variants={"10": "a", "30": "b"})
    blank_size = idea(variants={**VARIANTS, "100": " "})
    no_title = idea(title="")
    items = coach.parse_answer(json.dumps([bad_sizes, blank_size, no_title, idea(title="Keep me")]))
    assert [i["title"] for i in items] == ["Keep me"]


def test_parse_blanks_unsafe_link_and_unknown_type():
    item = coach.parse_answer(json.dumps([idea(source_url="javascript:alert(1)", source_type="blog")]))[0]
    assert item["source_url"] == ""
    assert item["source_type"] == ""


def test_parse_keeps_real_area_else_default():
    assert coach.parse_answer(json.dumps([idea(area="Health")]), "Study")[0]["area"] == "Health"
    assert coach.parse_answer(json.dumps([idea(area="Cooking")]), "Study")[0]["area"] == "Study"


def test_parse_keeps_at_most_five():
    assert len(coach.parse_answer(json.dumps([idea(title=f"T{i}") for i in range(8)]))) == 5


def test_parse_errors():
    with pytest.raises(ValueError):
        coach.parse_answer("not json")
    with pytest.raises(ValueError):
        coach.parse_answer("[]")
    with pytest.raises(ValueError):
        coach.parse_answer(json.dumps([{"title": "x"}]))
