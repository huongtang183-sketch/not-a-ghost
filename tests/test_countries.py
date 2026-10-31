from ghost import countries


def test_codes_are_two_capital_letters_and_names_are_unique():
    assert all(len(c) == 2 and c.isupper() for c in countries.COUNTRIES)
    names = list(countries.COUNTRIES.values())
    assert len(names) == len(set(names))
    assert len(names) > 190


def test_alias_codes_exist():
    assert all(code in countries.COUNTRIES for code in countries.ALIASES.values())


def test_first_letters_find_the_country():
    assert countries.search("jap") == [{"kind": "country", "name": "Japan"}]
    assert {"kind": "country", "name": "Switzerland"} in countries.search("swi")
    assert countries.search("JAP") == countries.search("jap")


def test_too_short_gives_nothing():
    assert countries.search("ja") == []


def test_alias_and_region():
    assert countries.search("usa") == [{"kind": "country", "name": "United States"}]
    assert {"kind": "region", "name": "Europe"} in countries.search("eur")


def test_country_name_falls_back_to_the_code():
    assert countries.country_name("JP") == "Japan"
    assert countries.country_name("ZZ") == "ZZ"
