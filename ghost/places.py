"""City search for Ghost: type the first letters, get matching cities.

Data: GeoNames (https://www.geonames.org), licensed CC BY 4.0.

Try it:
    python -m ghost.places zur
"""
import csv
import sys
import unicodedata
from bisect import bisect_left
from collections import namedtuple
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "places.csv"
EXTRA = {"đ": "d", "ø": "o", "ł": "l", "ß": "ss", "æ": "ae", "œ": "oe"}
MIN_CHARS = 3
LIMIT = 8
DISTRICT = "PPLX"  # sub-districts such as "Zürich (Kreis 4)"

Place = namedtuple("Place", "id name country lat lng population timezone")


def plain(text):
    """Lowercase, strip accents and extra spaces: 'Zürich' becomes 'zurich'."""
    text = "".join(EXTRA.get(c, c) for c in text.lower())
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


def load(path=DATA):
    """Read places.csv. Returns (places, keys): keys is a sorted list of
    (search text, place number) covering each place's name and ASCII name."""
    places, keys = [], []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["feature"] == DISTRICT:
                continue
            place = Place(row["id"], row["name"], row["country"], float(row["lat"]),
                          float(row["lng"]), int(row["population"]), row["timezone"])
            number = len(places)
            places.append(place)
            for text in {plain(row["name"]), plain(row["ascii"])}:
                keys.append((text, number))
    keys.sort()
    return places, keys


def search(index, query, limit=LIMIT):
    """Cities whose name starts with the query, largest first."""
    places, keys = index
    q = plain(query)
    if len(q) < MIN_CHARS:
        return []
    start = bisect_left(keys, (q, -1))
    found = set()
    while start < len(keys) and keys[start][0].startswith(q):
        found.add(keys[start][1])
        start += 1
    ranked = sorted((places[n] for n in found), key=lambda p: (-p.population, p.name))
    return ranked[:limit]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m ghost.places <first letters>")
    index = load()
    results = search(index, " ".join(sys.argv[1:]))
    if not results:
        print(f"No city found (type at least {MIN_CHARS} letters).")
    for p in results:
        print(f"{p.name}, {p.country}  population {p.population:,}  ({p.lat:.2f}, {p.lng:.2f})  {p.timezone}")


if __name__ == "__main__":
    main()
