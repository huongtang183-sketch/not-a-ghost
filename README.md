# Ghost

A small local web app with two pages.

- **Improve your life.** Describe an activity and get sourced ideas to do it differently, spend less, or find something similar. Start a trial, track one number, and log each day in a notebook.
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
