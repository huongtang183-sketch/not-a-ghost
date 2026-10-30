"""Activity suggestions for the log box: type a few letters, get matching activities.

Matches come from a built-in list and from the user's own earlier entries.
Your own entries rank first, then the more often you logged one, the higher it ranks.
"""
from ghost.places import plain

MIN_CHARS = 2
LIMIT = 8

BUILT_IN = {
    "Study": [
        "Reading a textbook chapter", "Doing practice problems", "Taking notes", "Reviewing flashcards",
        "Watching a lecture", "Writing an essay", "Learning a language", "Practising vocabulary",
        "Studying for an exam", "Working through past exam papers", "Learning to code", "Reading a research paper",
        "Learning an instrument", "Reading a book", "Revising statistics", "Revising maths",
        "Doing homework", "Attending a class", "Studying in the library", "Listening to a podcast to learn",
    ],
    "Work": [
        "Deep work session", "Answering emails", "Planning the day", "Writing code", "Reviewing code",
        "Writing a report", "Preparing a presentation", "Attending meetings", "Job applications",
        "Networking", "Writing a cover letter", "Updating my CV", "Interview preparation",
        "Working on a side project", "Managing tasks", "Writing documentation", "Debugging",
        "Data analysis", "Client calls", "Brainstorming ideas",
    ],
    "Health": [
        "Morning run", "Evening run", "Going for a walk", "Gym workout", "Strength training", "Yoga",
        "Stretching", "Cycling", "Swimming", "Meditation", "Going to bed early", "Afternoon nap",
        "Drinking water", "Cooking a healthy meal", "Eating breakfast", "Intermittent fasting",
        "Morning routine", "Evening routine", "Screen-free hour", "Hiking", "Dancing", "Physiotherapy exercises",
    ],
    "Style": [
        "Wearing a blazer", "Wearing a shirt", "Wearing a dress", "Wearing a suit", "Wearing sneakers",
        "Wearing a coat", "Planning an outfit", "Wearing a tie", "Wearing a scarf", "Wearing jeans",
        "Skincare routine", "Hair care routine", "Wearing a watch", "Wearing jewellery",
        "Wearing a jacket", "Wearing makeup", "Trying a new haircut", "Tidying my wardrobe",
    ],
    "Money": [
        "Tracking expenses", "Making a budget", "Cooking instead of eating out", "Cancelling a subscription",
        "Comparing prices", "Meal planning", "Saving a fixed amount", "Reviewing my bank statement",
        "Buying second-hand", "Paying a bill", "Reading about investing", "No-spend day",
        "Shopping with a list", "Selling something I no longer use",
    ],
    "Other": [
        "Cleaning the house", "Doing laundry", "Gardening", "Cooking dinner", "Journaling", "Drawing",
        "Playing music", "Photography", "Calling a friend", "Spending time with family", "Volunteering",
        "Commuting", "Decluttering", "Writing for fun", "Playing a game", "Watching a film",
        "Praying", "Tidying my desk", "Planning a trip", "Caring for a pet",
    ],
}


def suggest(query, history=(), limit=LIMIT):
    """Activities matching the query, as dicts with text, area and source ("yours" or "list").

    history: earlier entries as dicts with text and area, oldest first.
    """
    q = plain(query)
    if len(q) < MIN_CHARS:
        return []
    candidates = {}  # plain text -> [text, area, count, source]
    for area, names in BUILT_IN.items():
        for name in names:
            candidates[plain(name)] = [name, area, 0, "list"]
    for entry in history:
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        key = plain(text)
        item = candidates.get(key)
        if item is None or item[3] == "list":
            item = candidates[key] = [text, entry.get("area") or "Other", 0, "yours"]
        item[0], item[1] = text, entry.get("area") or item[1]
        item[2] += 1
    ranked = []
    for key, (text, area, count, source) in candidates.items():
        if key.startswith(q):
            tier = 0
        elif (" " + q) in (" " + key):
            tier = 1
        else:
            continue
        ranked.append(((tier, source != "yours", -count, key), {"text": text, "area": area, "source": source}))
    ranked.sort(key=lambda r: r[0])
    return [item for _, item in ranked[:limit]]
