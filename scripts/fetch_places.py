"""Download the GeoNames city list and keep only the fields Ghost uses.

Source: GeoNames (https://www.geonames.org), licensed CC BY 4.0.

Usage:
    python scripts/fetch_places.py             download, then build data/places.csv
    python scripts/fetch_places.py --zip FILE  build from a zip you already have
"""
import argparse
import csv
import io
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

URL = "https://download.geonames.org/export/dump/cities15000.zip"
DATA = Path(__file__).resolve().parent.parent / "data"
COLUMNS = ["id", "name", "ascii", "country", "feature", "lat", "lng", "population", "timezone"]
EXTRA = {"\u0111": "d", "\u00f8": "o", "\u0142": "l", "\u00df": "ss", "\u00e6": "ae", "\u0153": "oe"}


def plain(text):
    """Lowercase and strip accents: 'Zürich' becomes 'zurich'."""
    text = "".join(EXTRA.get(c, c) for c in text.lower())
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ghost-app/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        dest.write_bytes(response.read())


def parse(zip_path):
    """Read the GeoNames table (tab separated, no header, 19 columns)."""
    rows = []
    with zipfile.ZipFile(zip_path) as archive:
        txt = next(n for n in archive.namelist() if n.endswith(".txt") and "readme" not in n.lower())
        with archive.open(txt) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 19:
                    continue
                rows.append({
                    "id": parts[0],
                    "name": parts[1],
                    "ascii": parts[2],
                    "country": parts[8],
                    "feature": parts[7],
                    "lat": float(parts[4]),
                    "lng": float(parts[5]),
                    "population": int(parts[14] or 0),
                    "timezone": parts[17],
                })
    return rows


def write_csv(rows, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows, path):
    print(f"Places: {len(rows)}")
    print(f"Countries: {len({r['country'] for r in rows})}")
    print(f"Latitude range: {min(r['lat'] for r in rows):.2f} to {max(r['lat'] for r in rows):.2f}")
    print(f"Longitude range: {min(r['lng'] for r in rows):.2f} to {max(r['lng'] for r in rows):.2f}")
    print(f"File: {path} ({path.stat().st_size / 1e6:.2f} MB)")
    print("Largest five:")
    for r in sorted(rows, key=lambda r: -r["population"])[:5]:
        print(f"  {r['name']}, {r['country']}  population {r['population']:,}  ({r['lat']:.2f}, {r['lng']:.2f})  {r['timezone']}")
    print("Feature codes:", Counter(r["feature"] for r in rows).most_common(6))
    for query in ("zurich", "seoul", "hanoi", "da nang"):
        hits = sorted((r for r in rows if query in (plain(r["name"]), plain(r["ascii"]))), key=lambda r: -r["population"])
        if hits:
            h = hits[0]
            print(f"{query}: {h['name']}, {h['country']}, {h['feature']} ({h['lat']:.2f}, {h['lng']:.2f})")
        else:
            print(f"{query}: not found")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, help="use this zip file instead of downloading")
    args = parser.parse_args()

    zip_path = args.zip or DATA / "cities15000.zip"
    if not args.zip:
        print(f"Downloading {URL}")
        download(URL, zip_path)
    rows = parse(zip_path)
    if not rows:
        raise SystemExit("No rows were read. Check that the zip holds the GeoNames city table.")
    out = DATA / "places.csv"
    DATA.mkdir(parents=True, exist_ok=True)
    write_csv(rows, out)
    summarize(rows, out)
    print("Place data: GeoNames, CC BY 4.0 (credit required).")


if __name__ == "__main__":
    main()
    