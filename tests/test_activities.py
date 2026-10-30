from ghost import activities


def texts(results):
    return [r["text"] for r in results]


def test_every_built_in_area_is_valid():
    assert set(activities.BUILT_IN) == {"Study", "Work", "Health", "Style", "Money", "Other"}


def test_prefix_match_with_area():
    found = activities.suggest("morn")
    assert "Morning run" in texts(found)
    assert {r["text"]: r["area"] for r in found}["Morning run"] == "Health"


def test_matches_a_later_word():
    assert "Morning run" in texts(activities.suggest("run"))


def test_phrase_start_ranks_before_later_word():
    history = [{"text": "Running club", "area": "Health"}]
    found = texts(activities.suggest("run", history))
    assert found.index("Running club") < found.index("Morning run")


def test_case_and_accent_insensitive():
    assert texts(activities.suggest("WEAR")) == texts(activities.suggest("wear"))
    assert activities.suggest("cafe") == activities.suggest("café")


def test_too_short_returns_nothing():
    assert activities.suggest("m") == []


def test_no_match():
    assert activities.suggest("qqqq") == []


def test_own_entries_come_first():
    history = [{"text": "Reading about Japanese woodworking", "area": "Other"}]
    found = activities.suggest("read", history)
    assert found[0] == {"text": "Reading about Japanese woodworking", "area": "Other", "source": "yours"}


def test_more_frequent_own_entry_ranks_higher():
    history = [{"text": "Running", "area": "Health"}, {"text": "Rugby", "area": "Health"}, {"text": "Rugby", "area": "Health"}]
    assert texts(activities.suggest("ru", history))[:2] == ["Rugby", "Running"]


def test_own_entry_replaces_the_built_in_one_without_duplicate():
    history = [{"text": "morning run", "area": "Other"}]
    found = [r for r in activities.suggest("morning", history) if r["text"].lower() == "morning run"]
    assert found == [{"text": "morning run", "area": "Other", "source": "yours"}]


def test_limit():
    assert len(activities.suggest("wear", limit=3)) == 3


def test_blank_history_entries_are_ignored():
    assert activities.suggest("zz", [{"text": "  ", "area": "Study"}, {}]) == []
