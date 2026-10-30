"""The Claude hand-off: build tonight's prompt, check the answer that comes back.

The prompt asks for a JSON list. Only ideas with a title and all four sizes
are accepted, and links must start with http or https.

Try it:
    python -m ghost.coach zurich
"""
import json
import re
import sys

from ghost import geo, places

AREAS = ["Study", "Work", "Health", "Style", "Money", "Other"]
SIZES = ["10", "30", "50", "100"]
SOURCE_TYPES = ["research", "person", "product"]
MAX_IDEAS = 5
ANYWHERE = "anywhere in the world"


def _names(titles):
    return "; ".join(titles) or "none"


def build_prompt(day=None, region="", limit="", count=1, kept=(), dropped=(), tried=(),
                 current="", goal="", keep_same="", may_change=""):
    """Prompt to paste into Claude with web search on.

    day: dict with area, text, minutes, solved, sleep, feel (or None).
    kept, dropped, tried: titles of ideas already decided, so Claude does not repeat them.
    current: how the user does it now. goal: what they want to improve.
    keep_same, may_change: what must stay the same, and what may differ, in the ideas returned.
    """
    region = (region or "").strip() or ANYWHERE
    limit = (limit or "").strip()
    ask = "ONE small change" if count == 1 else f"{count} different small changes"
    if day:
        area = day.get("area") or "Study"
        today = (f"What I did today: {day.get('text') or area} (area: {area}), {day.get('minutes', 0)} minutes, "
                 f"{day.get('solved', 0)} items finished, slept {day.get('sleep')} hours, felt {day.get('feel')} out of 5.")
    else:
        today = "I have not logged a day yet, so suggest a change for how I study."
    details = []
    if (current or "").strip():
        details.append(f"How I do it now: {current.strip()}.")
    if (goal or "").strip():
        details.append(f"My goal: {goal.strip()}.")
    if (keep_same or "").strip():
        details.append(f"Keep the same: {keep_same.strip()}.")
    if (may_change or "").strip():
        details.append(f"Open to changing: {may_change.strip()}.")
    return "\n".join([
        f"You are my daily coach. Find how other people around the world do the same thing as me in a different way, and suggest {ask} I can try tomorrow.",
        today,
        *details,
        f"Examples should come from: {region}." + (f" My limit: {limit}." if limit else ""),
        "Search the web. Use only sources you opened and give each link. If you cannot find a source, say so in \"why\" and leave the link empty. "
        "Do not invent people, quotes or numbers. Say whether each source is research, a person’s own account, or a product listing. "
        "Never suggest cutting sleep or anything risky. If I attached a photo, use it.",
        f"Do not repeat. Kept: {_names(kept)}. Dropped: {_names(dropped)}. Already tried: {_names(tried)}.",
        "Write each change at four sizes: 10%, 30%, 50% and 100% of the full change, from a small first step to the whole thing.",
        'Reply with a JSON array only, one object per change: [{"title":"","why":"","source_type":"research|person|product",'
        '"from":"","source_title":"","source_url":"","variants":{"10":"","30":"","50":"","100":""}}]',
    ])


def region_hint(index, place):
    """Region text for the prompt: the city opposite `place` on the globe."""
    there, _ = geo.opposite(index, place)
    return f"around {there.name}, {there.country} (the opposite side of the world from {place.name}, {place.country})"


def parse_answer(text, default_area="Other"):
    """Turn Claude's reply into a list of valid ideas. Raises ValueError if none is valid."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("The answer is not valid JSON.") from error
    items = []
    for x in (data if isinstance(data, list) else [data])[:MAX_IDEAS]:
        if not isinstance(x, dict) or not isinstance(x.get("title"), str) or not x["title"].strip():
            continue
        variants = x.get("variants")
        if not isinstance(variants, dict) or not all(isinstance(variants.get(k), str) and variants[k].strip() for k in SIZES):
            continue
        url = str(x.get("source_url") or "")
        items.append({
            "title": x["title"],
            "area": x["area"] if x.get("area") in AREAS else default_area,
            "why": str(x.get("why") or ""),
            "source_type": x["source_type"] if x.get("source_type") in SOURCE_TYPES else "",
            "from": str(x.get("from") or ""),
            "source_title": str(x.get("source_title") or ""),
            "source_url": url if re.match(r"https?://", url) else "",
            "variants": {k: variants[k] for k in SIZES},
        })
    if not items:
        raise ValueError("No idea has a title and all four sizes (10, 30, 50, 100).")
    return items


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m ghost.coach <your city>")
    index = places.load()
    found = places.search(index, " ".join(sys.argv[1:]), limit=1)
    if not found:
        raise SystemExit("No city found (type at least 3 letters).")
    example = {"area": "Study", "text": "Revised statistics by rereading notes", "minutes": 90, "solved": 6, "sleep": 7, "feel": 3}
    print(build_prompt(example, region=region_hint(index, found[0])))


if __name__ == "__main__":
    main()
