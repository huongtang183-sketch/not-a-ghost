"""The request to Claude and the check of its answer.

The request asks for a JSON list of ideas. An idea is kept only if it has a title,
a summary and at least one benefit; links must start with http or https.

Try it:
    python -m ghost.coach zurich
"""
import json
import re
import sys


AREAS = ["Study", "Work", "Health", "Style", "Money", "Other"]
SOURCE_TYPES = ["research", "person", "product"]
MAX_IDEAS = 10
MAX_BENEFITS = 3
MAX_BENEFIT_CHARS = 160
MAX_PRICE_CHARS = 80
MODES = ["improve", "cheaper", "similar"]
ANYWHERE = "anywhere in the world"
MODE_RULES = {
    "improve": "",
    "cheaper": "The alternative must do the same job as mine at a lower price. If its quality or features differ, say so in the summary.",
    "similar": "The suggestion must share something concrete with my example, and the summary says what it shares.",
}
SUMMARY_FOCUS = {
    "improve": "what people do and why it works",
    "cheaper": "what the alternative is and how it matches mine",
    "similar": "what it is and what it shares with my example",
}
BENEFIT_FOCUS = {
    "improve": "my goal",
    "cheaper": "what stays the same and what I save",
    "similar": "what is alike",
}


def build_prompt(request, region="", limit="", count=1, keep_same="", tried=(), mode="improve", links=(), photos=0):
    """Request text for Claude (web search on).

    request: the user's description of what they do and want to improve.
    tried: titles of ideas the user already started, so Claude does not repeat them.
    mode: improve (do it differently), cheaper (same job at a lower price) or similar (something alike).
    """
    mode = mode if mode in MODES else "improve"
    searches, pages = 3 + 2 * count, 2 + count
    region = (region or "").strip() or ANYWHERE
    limit = (limit or "").strip()
    ask = "ONE idea" if count == 1 else f"{count} different ideas"
    if mode == "cheaper":
        lines = [
            f"Find a cheaper equivalent of what I buy or use, and give me {ask} I can switch to.",
            f"What I buy or use now (with its price if I know it): {request.strip()}",
        ]
    elif mode == "similar":
        lines = [
            f"Find something similar to what I describe that I may not know yet, and give me {ask} I can try.",
            f"What I like or use now: {request.strip()}",
        ]
    else:
        lines = [
            f"Find how other people do the same thing as me in a different way, and give me {ask} I can try.",
            f"What I do and what I want to improve: {request.strip()}",
        ]
    if (keep_same or "").strip():
        lines.append(f"Keep the same: {keep_same.strip()}.")
    lines += [
        f"Examples should come from: {region}." + (f" My limit: {limit}." if limit else ""),
        "Stay strictly on my activity and my numbers. Do not bring in other topics, interviews or anything unrelated.",
        *(MODE_RULES[mode],),
        f"Search the web, with at most {searches} searches and {pages} pages opened. Give each link. "
        "Every idea needs a source_url taken from your search results or from a page you opened; never write a link you did not see. "
        "Leave out any idea you cannot source. "
        "Do not invent people, quotes or numbers. "
        "Never suggest anything risky, such as cutting sleep.",
        "Write like a short magazine article: no first person and no comments about your searching or checking. "
        f"summary: 2 or 3 sentences on {SUMMARY_FOCUS[mode]}. "
        f"benefits: 2 or 3 short phrases, each under 12 words, on {BENEFIT_FOCUS[mode]}. "
        "from: the place or people the idea comes from. "
        "price: only if a page you opened shows it, with currency, such as \"CHF 49 instead of CHF 89\"; otherwise an empty string.",
    ]
    links = [str(x).strip() for x in links if re.match(r"https?://", str(x).strip())][:5]
    if links:
        lines.append("Open these links first; they show what I mean: " + " ".join(links))
    if photos:
        s = "s" if photos > 1 else ""
        lines.append(f"I attached {photos} photo{s} of it; use what you see in the photo{s}.")
    names = [t for t in tried if t]
    if names:
        lines.append("Do not repeat these: " + "; ".join(names) + ".")
    lines.append(
        'Reply with a JSON array only: [{"title":"","area":"Study|Work|Health|Style|Money|Other","summary":"",'
        '"benefits":["",""],"source_type":"research|person|product","from":"","price":"","source_title":"","source_url":""}]')
    return "\n".join(line for line in lines if line)


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
        if not re.match(r"https?://", url):
            continue  # an idea without a source link is dropped
        items.append({
            "title": _clean(title),
            "area": x["area"] if x.get("area") in AREAS else default_area,
            "summary": _clean(summary),
            "benefits": benefits,
            "source_type": x["source_type"] if x.get("source_type") in SOURCE_TYPES else "",
            "from": _clean(x.get("from") or ""),
            "price": _clean(x.get("price") or "")[:MAX_PRICE_CHARS] if isinstance(x.get("price"), str) else "",
            "source_title": _clean(x.get("source_title") or ""),
            "source_url": url,
        })
    if not items:
        raise ValueError("No idea has a title, a summary, at least one benefit and a source link.")
    return items


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    request = " ".join(sys.argv[1:]) or "I run 5 km three times a week at 6:30 per km and want to get faster"
    print(build_prompt(request))


if __name__ == "__main__":
    main()
