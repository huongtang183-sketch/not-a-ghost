import json

import pytest

from ghost import coach

REQUEST = "I run 5 km three times a week at 6:30 per km and want to get faster"


def idea(**changes):
    base = {"title": "Add strides after easy runs", "area": "Health", "summary": "Runners finish easy runs with short fast strides.",
            "benefits": ["Faster turnover", "Little extra time"], "source_type": "research", "from": "Kenya",
            "source_title": "A study", "source_url": "https://example.org/x"}
    base.update(changes)
    return base


def test_prompt_contains_the_request_and_the_rules():
    p = coach.build_prompt(REQUEST)
    assert f"What I do and what I want to improve: {REQUEST}" in p
    assert "ONE idea" in p
    assert "Stay strictly on my activity and my numbers" in p
    assert "at most 3 searches" in p
    assert "never write a link you did not see" in p
    assert "Never suggest anything risky" in p
    assert "no first person and no comments about your searching or checking" in p
    assert "Reply with a JSON array only" in p


def test_prompt_asks_for_article_fields_and_no_sizes():
    p = coach.build_prompt(REQUEST)
    assert '"summary":""' in p and '"benefits":["",""]' in p
    assert '"area":"Study|Work|Health|Style|Money|Other"' in p
    assert "variants" not in p


def test_prompt_defaults_region_and_limit():
    p = coach.build_prompt(REQUEST)
    assert "Examples should come from: anywhere in the world." in p
    assert "My limit" not in p
    assert "My limit: under 10 CHF." in coach.build_prompt(REQUEST, limit="under 10 CHF")
    assert "Examples should come from: Japan." in coach.build_prompt(REQUEST, region="Japan")


def test_prompt_count():
    assert "ONE idea" in coach.build_prompt(REQUEST, count=1)
    assert "3 different ideas" in coach.build_prompt(REQUEST, count=3)


def test_prompt_keep_same_and_tried():
    p = coach.build_prompt(REQUEST, keep_same="Three sessions a week", tried=["A", "B"])
    assert "Keep the same: Three sessions a week." in p
    assert "Do not repeat these: A; B." in p
    plain = coach.build_prompt(REQUEST)
    assert "Keep the same" not in plain and "Do not repeat" not in plain


def test_parse_valid_list():
    item = coach.parse_answer(json.dumps([idea()]), "Study")[0]
    assert item["title"] == "Add strides after easy runs"
    assert item["area"] == "Health"
    assert item["benefits"] == ["Faster turnover", "Little extra time"]
    assert item["source_type"] == "research"
    assert item["source_url"] == "https://example.org/x"


def test_parse_accepts_code_fence_and_single_object():
    assert len(coach.parse_answer("```json\n" + json.dumps(idea()) + "\n```")) == 1


def test_parse_reads_a_list_surrounded_by_text():
    text = "Here are the ideas:\n" + json.dumps([idea()]) + "\nHope this helps."
    assert coach.parse_answer(text)[0]["title"] == "Add strides after easy runs"


def test_parse_text_without_a_list_fails():
    with pytest.raises(ValueError):
        coach.parse_answer("no list here, only words [maybe")


def test_parse_drops_incomplete_ideas():
    bad = [idea(title=""), idea(summary=" "), idea(benefits=[]), idea(benefits="fast"), idea(title="Keep me")]
    assert [i["title"] for i in coach.parse_answer(json.dumps(bad))] == ["Keep me"]


def test_parse_limits_benefits_and_trims_text():
    long = "x" * 400
    item = coach.parse_answer(json.dumps([idea(benefits=["a", "b", "c", "d", long])]))[0]
    assert item["benefits"] == ["a", "b", "c"]
    item = coach.parse_answer(json.dumps([idea(benefits=[long])]))[0]
    assert len(item["benefits"][0]) == 160


def test_parse_collapses_white_space():
    item = coach.parse_answer(json.dumps([idea(title="  Two\n  lines ", summary="A  b\n c")]))[0]
    assert item["title"] == "Two lines" and item["summary"] == "A b c"


def test_parse_drops_ideas_without_a_web_source():
    answer = [idea(title="No link", source_url=""), idea(title="Unsafe", source_url="javascript:alert(1)"), idea(title="Good")]
    items = coach.parse_answer(json.dumps(answer))
    assert [i["title"] for i in items] == ["Good"]


def test_parse_fails_when_no_idea_has_a_source():
    with pytest.raises(ValueError):
        coach.parse_answer(json.dumps([idea(source_url="")]))


def test_parse_blanks_unknown_type():
    assert coach.parse_answer(json.dumps([idea(source_type="blog")]))[0]["source_type"] == ""


def test_parse_keeps_real_area_else_default():
    assert coach.parse_answer(json.dumps([idea(area="Money")]), "Study")[0]["area"] == "Money"
    assert coach.parse_answer(json.dumps([idea(area="Cooking")]), "Study")[0]["area"] == "Study"


def test_parse_keeps_at_most_ten():
    assert len(coach.parse_answer(json.dumps([idea(title=f"T{i}") for i in range(14)]))) == coach.MAX_IDEAS == 10


def test_parse_errors():
    with pytest.raises(ValueError):
        coach.parse_answer("not json")
    with pytest.raises(ValueError):
        coach.parse_answer("[]")
    with pytest.raises(ValueError):
        coach.parse_answer(json.dumps([{"title": "x"}]))


def test_parse_drops_an_idea_whose_benefits_are_all_unusable():
    assert [i["title"] for i in coach.parse_answer(json.dumps([idea(benefits=[" ", 3]), idea(title="Keep me")]))] == ["Keep me"]


def test_modes_change_the_request_and_ask_for_a_price():
    cheaper = coach.build_prompt("A blender at 89 CHF", mode="cheaper")
    similar = coach.build_prompt("I love Lisbon trams", mode="similar")
    improve = coach.build_prompt("I run 5 km")
    assert "cheaper equivalent" in cheaper and "lower price" in cheaper
    assert "similar to what I describe" in similar
    assert "in a different way" in improve and "\n\n" not in improve
    assert coach.build_prompt("x", mode="unknown") == coach.build_prompt("x")
    assert '"price"' in cheaper


def test_price_is_kept_only_as_short_text():
    base = {"title": "t", "summary": "s", "benefits": ["b"], "source_url": "https://example.org"}
    items = coach.parse_answer(json.dumps([dict(base, price="CHF 49 instead of CHF 89"), dict(base, price=5), dict(base, price="x" * 200)]))
    assert items[0]["price"] == "CHF 49 instead of CHF 89"
    assert items[1]["price"] == ""
    assert len(items[2]["price"]) == coach.MAX_PRICE_CHARS


def test_links_and_photos_appear_in_the_request():
    prompt = coach.build_prompt("a blender", mode="cheaper", links=["https://shop.example/b", "javascript:x", "not a link"], photos=2)
    assert "https://shop.example/b" in prompt and "javascript" not in prompt and "not a link" not in prompt
    assert "I attached 2 photos" in prompt
    assert "attached" not in coach.build_prompt("a blender")


def test_more_ideas_allow_more_searches():
    assert "at most 3 searches and 2 pages" in coach.build_prompt("x", count=1)
    assert "at most 8 searches and 8 pages" in coach.build_prompt("x", count=8)
