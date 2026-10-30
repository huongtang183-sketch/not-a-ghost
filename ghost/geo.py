"""Distance between cities and the city on the opposite side of the world.

Try it:
    python -m ghost.geo madrid
"""
import sys
from math import asin, cos, radians, sin, sqrt

from ghost import places

EARTH_RADIUS_KM = 6371.0088


def distance_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in kilometres (haversine formula)."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def antipode(lat, lng):
    """The point exactly opposite on the globe."""
    return -lat, lng - 180 if lng > 0 else lng + 180


def opposite(index, place):
    """The listed city closest to the point opposite `place`.
    Returns (city, km from the exact opposite point)."""
    lat, lng = antipode(place.lat, place.lng)
    best = min(index[0], key=lambda c: distance_km(lat, lng, c.lat, c.lng))
    return best, distance_km(lat, lng, best.lat, best.lng)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m ghost.geo <city name>")
    index = places.load()
    found = places.search(index, " ".join(sys.argv[1:]), limit=1)
    if not found:
        raise SystemExit("No city found (type at least 3 letters).")
    here = found[0]
    there, gap = opposite(index, here)
    print(f"{here.name}, {here.country}")
    print(f"Opposite side: {there.name}, {there.country} ({gap:,.0f} km from the exact opposite point)")
    print(f"Distance between them: {distance_km(here.lat, here.lng, there.lat, there.lng):,.0f} km")


if __name__ == "__main__":
    main()
