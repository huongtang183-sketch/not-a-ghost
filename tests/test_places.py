import csv

import pytest

from ghost import places

ROWS = [
    # id, name, ascii, country, feature, lat, lng, population, timezone
    ("1", "Zürich", "Zuerich", "CH", "PPLA", 47.37, 8.55, 341730, "Europe/Zurich"),
    ("2", "Zürich (Kreis 4)", "Zuerich (Kreis 4)", "CH", "PPLX", 47.37, 8.52, 30000, "Europe/Zurich"),
    ("3", "Zurich", "Zurich", "CA", "PPL", 43.42, -81.62, 900, "America/Toronto"),
    ("4", "Seoul", "Seoul", "KR", "PPLC", 37.57, 126.98, 10349312, "Asia/Seoul"),
    ("5", "Đà Nẵng", "Da Nang", "VN", "PPLA", 16.07, 108.22, 1134310, "Asia/Ho_Chi_Minh"),
    ("6", "Zurzach", "Zurzach", "CH", "PPL", 47.59, 8.29, 4000, "Europe/Zurich"),
]


@pytest.fixture
def index(tmp_path):
    path = tmp_path / "places.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow("id name ascii country feature lat lng population timezone".split())
        writer.writerows(ROWS)
    return places.load(path)


def names(results):
    return [(p.name, p.country) for p in results]


def test_plain_strips_accents_and_case():
    assert places.plain("Zürich") == "zurich"
    assert places.plain("Đà Nẵng") == "da nang"
    assert places.plain("  New   York ") == "new york"


def test_accent_free_prefix_finds_accented_name(index):
    assert names(places.search(index, "zuri"))[0] == ("Zürich", "CH")


def test_ascii_spelling_also_matches(index):
    assert ("Zürich", "CH") in names(places.search(index, "zuer"))


def test_districts_are_left_out(index):
    assert all("Kreis" not in n for n, _ in names(places.search(index, "zur")))


def test_ranked_by_population(index):
    assert names(places.search(index, "zur")) == [("Zürich", "CH"), ("Zurzach", "CH"), ("Zurich", "CA")]


def test_no_duplicate_when_both_spellings_match(index):
    assert len(places.search(index, "zur")) == 3


def test_vietnamese_name_with_space(index):
    assert names(places.search(index, "da n")) == [("Đà Nẵng", "VN")]


def test_too_short_returns_nothing(index):
    assert places.search(index, "ze") == []


def test_unknown_returns_nothing(index):
    assert places.search(index, "qqq") == []


def test_limit(index):
    assert len(places.search(index, "zur", limit=2)) == 2


@pytest.mark.skipif(not places.DATA.exists(), reason="run scripts/fetch_places.py first")
def test_real_data():
    real = places.load()
    assert names(places.search(real, "zuri"))[0] == ("Zürich", "CH")
    assert names(places.search(real, "seou"))[0] == ("Seoul", "KR")
    assert len(real[0]) > 30000
