import pytest

from ghost import geo, places


def city(name, country, lat, lng):
    return places.Place(name, name, country, lat, lng, 1000, "UTC")


def test_london_to_paris():
    assert geo.distance_km(51.5074, -0.1278, 48.8566, 2.3522) == pytest.approx(343.5, abs=1)


def test_quarter_of_the_equator():
    assert geo.distance_km(0, 0, 0, 90) == pytest.approx(10007.5, abs=1)


def test_same_point_is_zero():
    assert geo.distance_km(47.37, 8.55, 47.37, 8.55) == 0


def test_antipode():
    assert geo.antipode(47.37, 8.55) == pytest.approx((-47.37, -171.45))
    assert geo.antipode(-33.0, -70.0) == pytest.approx((33.0, 110.0))
    assert geo.antipode(0, 180) == (0, 0)
    assert geo.antipode(0, 0) == (0, 180)


def test_a_point_and_its_antipode_are_half_the_globe_apart():
    lat, lng = geo.antipode(47.37, 8.55)
    assert geo.distance_km(47.37, 8.55, lat, lng) == pytest.approx(20015, abs=5)


def test_opposite_picks_the_nearest_listed_city():
    madrid = city("Madrid", "ES", 40.42, -3.70)
    wellington = city("Wellington", "NZ", -41.29, 174.78)
    sydney = city("Sydney", "AU", -33.87, 151.21)
    index = ([madrid, wellington, sydney], [])
    best, gap = geo.opposite(index, madrid)
    assert best.name == "Wellington"
    assert gap < 200


@pytest.mark.skipif(not places.DATA.exists(), reason="run scripts/fetch_places.py first")
def test_real_data_madrid_is_opposite_new_zealand():
    index = places.load()
    madrid = places.search(index, "madrid")[0]
    assert geo.opposite(index, madrid)[0].country == "NZ"
