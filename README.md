# not a ghost

## Why I built it

I believe we judge what is possible by what our five senses show us, and that this keeps people in versions of themselves that no longer fit. Two people born at the same moment in different countries, from different backgrounds, can end up with very different options and very different feelings about themselves. I use quantum entanglement as an analogy for this: it is an inspiration, not a claim that physics explains it. The 2022 Nobel Prize in Physics honoured Aspect, Clauser and Zeilinger for experiments with entangled photons that showed the world behaves in ways everyday experience does not predict.

I also believe a new pattern, repeated, becomes a new person, and that a new pattern starts when you see a way of living you had not seen. Michael Levin of Tufts University works on a related idea in biology: cells store pattern memories in bioelectric networks, and "the genome does not directly specify your shape".

*not a ghost* is my attempt to make that practical. Describe something you do, for example running five times a week in Vietnam. The app finds how people in another country, such as Japan or Korea, do the same thing differently, with a checked source for every idea. You try one change and log your days. A second page, "What's your life juggling?", shows where your time goes and what type of person your days describe, so you can watch yourself change.

Why the name? Many days we run on autopilot, like the ghost of yesterday repeating itself. Let's redefine ourselves: we are no longer a ghost of the past.

Sources: [Nobel Prize in Physics 2022, press release](https://www.nobelprize.org/prizes/physics/2022/press-release/); [New Atlas on Michael Levin's work](https://newatlas.com/biology/levin-bioelectricity-cellular-intelligence-dna).

## What it does

A small web app with two pages.

- **Improve your life.** Describe an activity and get sourced ideas to do it differently, spend less, or find something similar. Start a trial with a routine and an optional target, and log each day in a notebook.
- **What's your life juggling?** Your logged days become balls in the air (bigger ball, more time), with a type bar that names your main type and your streak type.

![Improve your life](docs/improve.png)
![What's your life juggling?](docs/juggling.png)

## Try it online

Live demo: https://huongtang183-sketch.github.io/ghost/

The demo shows sample ideas, each with its real source, and page 2 can load sample days. Live search needs the local server below. On a phone, open the demo and choose "Add to Home Screen" to install it.

## Run

Requires Python 3.12 or later. The server uses only the standard library.

```
python -m ghost.server
```

Open http://127.0.0.1:8000.

Idea search runs through the [Claude Code](https://claude.com/claude-code) command line with your own login, so no API key is stored. Claude Code runs with only its web search and web fetch tools enabled.

## Design

- **Local only.** The server listens on 127.0.0.1. Your log and trials stay in the browser's local storage.
- **Sourced ideas only.** Claude's reply must be JSON. An idea is kept only if it has a title, a summary, at least one benefit and a source link starting with http or https (`ghost/coach.py`). A link that clearly does not open (unknown host, 404, 410, server error) drops the idea (`ghost/linkcheck.py`). If fewer ideas pass than you asked for, the server asks again for the missing ones.
- **Safe previews.** Source-article previews open public web addresses only, so a link cannot make the server read your own network (`ghost/preview.py`).
- **Location box.** City names come from [GeoNames](https://www.geonames.org) (CC BY 4.0). Download the cities file and save it as `data/places.csv`; it is not in this repository.

## Publish the demo

```
python -m tools.build_demo
```

This writes the static demo to `docs/`, which GitHub Pages serves (Settings, Pages, branch `main`, folder `/docs`).

## Tests

```
python -m pytest
```

## Layout

```
ghost/   server, search, prompt and answer checks, link check, city and activity lookup
web/     index.html (Improve your life), pattern.html (What's your life juggling?)
tools/   build_demo.py (static demo for GitHub Pages), make_icons.py
docs/    the published demo, plus README screenshots
tests/   one test file per module
```
