#!/usr/bin/env python3
"""Rebuild data/polls.js from the Wikipedia page listing 2027 first-round polls.

    python3 scripts/update_polls.py             # fetch the live page
    python3 scripts/update_polls.py page.txt    # parse a saved wikitext file
    python3 scripts/update_polls.py page.txt --out /tmp/polls.js

Wikipedia is used only as an index: every poll keeps the link to the pollster's
own publication (or the press article) that Wikipedia cites.

Reading the tables is done by road2027.wikitext (shared with the backtest);
this script keeps the site's choices: which candidates are tracked, since when.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import urllib.request
from pathlib import Path
from typing import Any

from road2027.jsdata import write_js
from road2027.wikitext import Poll, parse_polls

ROOT = Path(__file__).resolve().parent.parent

LOGGER = logging.getLogger("update_polls")

PAGE = "Opinion_polling_for_the_2027_French_presidential_election"
RAW_URL = f"https://en.wikipedia.org/w/index.php?title={PAGE}&action=raw"
INDEX_URL = f"https://en.wikipedia.org/wiki/{PAGE}"
USER_AGENT = "road-to-2027-poll-updater/1.0"
OUTPUT = ROOT / "data" / "polls.js"
HEADER = "/* Généré par scripts/update_polls.py : ne pas modifier à la main. */\n"
SINCE = "2024-07-01"  # after the 2024 dissolution: the current political landscape

# Wikipedia column name -> candidate id used by the site (see data/site.js)
TRACKED = {
    "Marine Le Pen": "lepen",
    "Jean-Luc Mélenchon": "melenchon",
    "Raphaël Glucksmann": "glucksmann",
    "Fabien Roussel": "roussel",
    "Gabriel Attal": "attal",
    "Édouard Philippe": "philippe",
    "Marine Tondelier": "tondelier",
    "David Lisnard": "lisnard",
}


def fetch_wikitext(source: Path | None) -> str:
    """The saved page if given, else the live page from Wikipedia."""
    if source:
        return source.read_text(encoding="utf-8")
    request = urllib.request.Request(RAW_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def tracked_scores(scenario: dict[str, float]) -> dict[str, float]:
    """{"Marine Le Pen": 31.0, "Éric Zemmour": 4.0} -> {"lepen": 31.0}"""
    return {TRACKED[name]: score for name, score in scenario.items() if name in TRACKED}


def other_scores(scenario: dict[str, float]) -> dict[str, float]:
    """Candidates tested in the same line-up but not tracked on the site (Zemmour, Lagarde, Riner...).

    Kept so the site can say who was tested and spot unusual line-ups.
    """
    return {name: score for name, score in scenario.items() if name not in TRACKED}


def to_site_poll(poll: Poll) -> dict[str, Any] | None:
    """The poll as data/polls.js stores it, or None if the site does not show it."""
    if poll.date < SINCE:
        return None
    scenarios = [tracked_scores(s) for s in poll.scenarios]
    if not any(scenarios):
        return None  # no tracked candidate in any line-up
    return {
        "firm": poll.firm, "url": poll.url, "start": poll.start, "date": poll.date,
        "sample": poll.sample, "scenarios": scenarios,
        "others": [other_scores(s) for s in poll.scenarios],  # same order as "scenarios"
    }


def build_payload(polls: list[Poll], fetched: dt.date) -> dict[str, Any]:
    site_polls = [p for p in map(to_site_poll, polls) if p]
    site_polls.sort(key=lambda p: (p["date"], p["firm"]))
    return {"fetched": fetched.isoformat(), "index": INDEX_URL, "polls": site_polls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", type=Path, help="saved wikitext (default: live page)")
    parser.add_argument("--out", type=Path, default=OUTPUT, help="output file (default: data/polls.js)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # min_vals=1: keep every row with a score, the site filters on tracked candidates itself.
    polls = parse_polls(fetch_wikitext(args.source), min_vals=1)
    payload = build_payload(polls, dt.date.today())
    write_js(args.out, "POLLS", payload, header=HEADER)
    LOGGER.info("%d sondages écrits dans %s (depuis %s)", len(payload["polls"]), args.out, SINCE)

    missing = [(p["firm"], p["date"]) for p in payload["polls"] if not p["url"]]
    if missing:
        LOGGER.warning("Sans lien source : %s", missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
