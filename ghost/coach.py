"""The request to Claude and the check of its answer.

The request asks for a JSON list of ideas. An idea is kept only if it has a title,
a summary and at least one benefit; links must start with http or https.

Try it:
    python -m ghost.coach zurich
"""
import json
import re
import sys

from ghost import places

AREAS = ["Study", "Work", "Health", "Style", "Money", "Other"]
SOURCE_TYPES = ["research", "person", "product"]
MAX_IDEAS = 5
MAX_BENEFITS = 3
MAX_BENEFIT_CHARS = 160
ANYWHERE = "anywhere in the world"


def build_prompt(request, region="", limit="", count=1, keep_same="", tried=()):
    """Request text for Claude (web search on).

    request: the user's description of what they do and want to improve.
    tried: titles of ideas the user already started, so Claude does not repeat them.
    """
    region = (region or "").strip() or ANYWHERE
    limit = (limit or "").strip()
    ask = "ONE idea" if count == 1 else f"{count} different ideas"
    lines = [
        f"Find how other people do the same thing as me in a different way, and give me {ask} I can try.",
        f"What I do and what I want to improve: {request.strip()}",
    ]
    if (keep_same or "").strip():
        lines.append(f"Keep the same: {keep_same.strip()}.")
    lines += [
        f"Examples should come from: {region}." + (f" My limit: {limit}." if limit else ""),
        "Stay strictly on my activity and my numbers. Do not bring in other topics, interviews or anything unrelated.",
        "Search the web, with at most 3 searches and 2 pages opened. Use only sources you opened and give each link. "
        "If you cannot find a source, leave source_url empty. Do not invent people, quotes or numbers. "
        "Never suggest anything risky, such as cutting sleep.",
        "Write like a short magazine article: no first person and no comments about your searching or checking. "
        "summary: 2 or 3 sentences on what people do and why it works. "
        "benefits: 2 or 3 short phrases, each under 12 words and tied to my goal. "
        "from: the place or people the idea comes from.",
    ]
    names = [t for t in tried if t]
    if names:
        lines.append("Do not repeat these: " + "; ".join(names) + ".")
    lines.append(
        'Reply with a JSON array only: [{"title":"","area":"Study|Work|Health|Style|Money|Other","summary":"",'
        '"benefits":["",""],"source_type":"research|person|product","from":"","source_title":"","source_url":""}]')
    return "\n".join(lines)


def _clean(text):
    return " ".join(str(text).split())


def parse_answer(text, default_area="Other"):
    """Turn Claude's reply into a list of valid ideas. Raises ValueError if none is valid."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        # Claude sometimes adds a sentence around the list: keep what lies between the outer brackets.
        start, end = cleaned.find("["), cleaned.rfind("]")
        try:
            if start < 0 or end <= start:
                raise ValueError
            data = json.loads(cleaned[start:end + 1])
        except ValueError:
            raise ValueError("The answer is not valid JSON.") from error
    items = []
    for x in (data if isinstance(data, list) else [data])[:MAX_IDEAS]:
        if not isinstance(x, dict):
            continue
        title, summary = x.get("title"), x.get("summary")
        benefits = x.get("benefits")
        if not (isinstance(title, str) and title.strip() and isinstance(summary, str) and summary.strip()):
            continue
        if not isinstance(benefits, list):
            continue
        benefits = [_clean(b)[:MAX_BENEFIT_CHARS] for b in benefits if isinstance(b, str) and b.strip()][:MAX_BENEFITS]
        if not benefits:
            continue
        url = str(x.get("source_url") or "")
        items.append({
            "title": _clean(title),
            "area": x["area"] if x.get("area") in AREAS else default_area,
            "summary": _clean(summary),
            "benefits": benefits,
            "source_type": x["source_type"] if x.get("source_type") in SOURCE_TYPES else "",
            "from": _clean(x.get("from") or ""),
            "source_title": _clean(x.get("source_title") or ""),
            "source_url": url if re.match(r"https?://", url) else "",
        })
    if not items:
        raise ValueError("No idea has a title, a summary and at least one benefit.")
    return items


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    request = " ".join(sys.argv[1:]) or "I run 5 km three times a week at 6:30 per km and want to get faster"
    print(build_prompt(request))


if __name__ == "__main__":
    main()
