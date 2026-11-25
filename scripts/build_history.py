#!/usr/bin/env python3
"""Build data/history.js: first-round polls and results of the 2002-2022 presidential elections.

    python3 scripts/build_history.py

Source: the Wikipedia poll pages saved in backtest/raw/polls_YYYY.txt (parsed with
road2027.wikitext). Only the national first-round tables are read: the "By region / department /
commune / constituency" sections hold regional polls (La Réunion, PACA, Corsica...) that are not
comparable with national ones.

For each election the site follows the 8 candidates with the best first-round result. Each poll is
read in one line-up (scenario), chosen with the same rule as the 2027 pages (app.js, lineup()):
the line-up closest to the standard field of the previous 60 days, minus a penalty for each
unusual name. This is what the polls said at the time, not a hindsight selection.
Poll medians at a given day before the vote ("J-145") are computed in the browser (app.js, snapshot()).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import sys
from pathlib import Path
from typing import Any

from road2027.jsdata import write_js
from road2027.wikitext import parse

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "backtest" / "raw"
OUTPUT = ROOT / "data" / "history.js"
HEADER = "/* Généré par scripts/build_history.py : ne pas modifier à la main. */\n"
LOGGER = logging.getLogger("build_history")

# Same constants as app.js (lineup()), so a past poll is read the way a 2027 poll is.
STD_DAYS, STD_SHARE, EXTRA_PENALTY = 60, 0.5, 1.5

REGIONAL = re.compile(r"by (region|department|commune|constituency)", re.I)
HEADING = re.compile(r"^=+\s*(.*?)\s*=+\s*$", re.M)

WIKI_FR = "https://fr.wikipedia.org/wiki/%C3%89lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_{}"
POLLS_EN = "https://en.wikipedia.org/wiki/Opinion_polling_for_the_{}_French_presidential_election"

# Per election: date of the first round, the 8 followed candidates (name as in the Wikipedia
# tables -> id, short name, party, colour slot 1-8 of the palette), the second round
# (% of valid votes, Conseil constitutionnel) and dated campaign events.
# Colour slots follow the political family where possible (1 FN/RN, 5 PS, 7 RPR/UMP/LR,
# 8 radical left, 4 Macron...), so a family keeps a similar hue from one election to the next.
ELECTIONS: dict[int, dict[str, Any]] = {
    2002: {
        "date": "2002-04-21",
        "candidates": [
            ("Jacques Chirac", "chirac", "Chirac", "RPR", 7),
            ("Jean-Marie Le Pen", "jmlepen", "J.-M. Le Pen", "Front national", 1),
            ("Lionel Jospin", "jospin", "Jospin", "Parti socialiste", 5),
            ("François Bayrou", "bayrou", "Bayrou", "UDF", 3),
            ("Arlette Laguiller", "laguiller", "Laguiller", "Lutte ouvrière", 8),
            ("Jean-Pierre Chevènement", "chevenement", "Chevènement", "Pôle républicain", 2),
            ("Noël Mamère", "mamere", "Mamère", "Les Verts", 6),
            ("Olivier Besancenot", "besancenot", "Besancenot", "LCR", 4),
        ],
        "second": {"chirac": 82.21, "jmlepen": 17.79},
        "events": [
            ("2001-09-04", "Jean-Pierre Chevènement annonce sa candidature", "Chevènement candidat", ["chevenement"]),
            ("2002-02-11", "Jacques Chirac annonce sa candidature à Avignon", "Chirac candidat", ["chirac"]),
            ("2002-02-20", "Lionel Jospin annonce sa candidature", "Jospin candidat", ["jospin"]),
            ("2002-04-18", "Agression de Paul Voise à Orléans, très médiatisée à la veille du vote", "Affaire Voise", []),
        ],
    },
    2007: {
        "date": "2007-04-22",
        "candidates": [
            ("Nicolas Sarkozy", "sarkozy", "Sarkozy", "UMP", 7),
            ("Ségolène Royal", "royal", "Royal", "Parti socialiste", 5),
            ("François Bayrou", "bayrou", "Bayrou", "UDF", 3),
            ("Jean-Marie Le Pen", "jmlepen", "J.-M. Le Pen", "Front national", 1),
            ("Olivier Besancenot", "besancenot", "Besancenot", "LCR", 8),
            ("Philippe de Villiers", "villiers", "de Villiers", "Mouvement pour la France", 4),
            ("Marie-George Buffet", "buffet", "Buffet", "Parti communiste français", 2),
            ("Dominique Voynet", "voynet", "Voynet", "Les Verts", 6),
        ],
        "second": {"sarkozy": 53.06, "royal": 46.94},
        "events": [
            ("2006-11-16", "Ségolène Royal remporte la primaire socialiste", "Primaire PS", ["royal"]),
            ("2007-01-14", "Nicolas Sarkozy investi candidat de l'UMP", "Sarkozy investi", ["sarkozy"]),
            ("2007-03-11", "Jacques Chirac annonce qu'il ne se représente pas", "Chirac renonce", []),
            ("2007-03-27", "Incidents de la gare du Nord à Paris", "Gare du Nord", []),
        ],
    },
    2012: {
        "date": "2012-04-22",
        "candidates": [
            ("François Hollande", "hollande", "Hollande", "Parti socialiste", 5),
            ("Nicolas Sarkozy", "sarkozy", "Sarkozy", "UMP", 7),
            ("Marine Le Pen", "lepen", "Le Pen", "Front national", 1),
            ("Jean-Luc Mélenchon", "melenchon", "Mélenchon", "Front de gauche", 8),
            ("François Bayrou", "bayrou", "Bayrou", "MoDem", 3),
            ("Eva Joly", "joly", "Joly", "Europe Écologie Les Verts", 6),
            ("Nicolas Dupont-Aignan", "dupontaignan", "Dupont-Aignan", "Debout la République", 4),
            ("Philippe Poutou", "poutou", "Poutou", "NPA", 2),
        ],
        "second": {"hollande": 51.64, "sarkozy": 48.36},
        "events": [
            ("2011-05-14", "Dominique Strauss-Kahn, favori des sondages, arrêté à New York", "Arrestation DSK", []),
            ("2011-10-16", "François Hollande remporte la primaire socialiste", "Primaire PS", ["hollande"]),
            ("2012-01-22", "Discours de François Hollande au Bourget", "Le Bourget", ["hollande"]),
            ("2012-02-15", "Nicolas Sarkozy annonce sa candidature", "Sarkozy candidat", ["sarkozy"]),
            ("2012-03-11", "Tueries de Toulouse et Montauban (11 au 22 mars)", "Toulouse", [], "2012-03-22"),
        ],
    },
    2017: {
        "date": "2017-04-23",
        "candidates": [
            ("Emmanuel Macron", "macron", "Macron", "En marche !", 4),
            ("Marine Le Pen", "lepen", "Le Pen", "Front national", 1),
            ("François Fillon", "fillon", "Fillon", "Les Républicains", 7),
            ("Jean-Luc Mélenchon", "melenchon", "Mélenchon", "La France insoumise", 8),
            ("Benoît Hamon", "hamon", "Hamon", "Parti socialiste", 5),
            ("Nicolas Dupont-Aignan", "dupontaignan", "Dupont-Aignan", "Debout la France", 3),
            ("Jean Lassalle", "lassalle", "Lassalle", "Résistons !", 6),
            ("Philippe Poutou", "poutou", "Poutou", "NPA", 2),
        ],
        "second": {"macron": 66.10, "lepen": 33.90},
        "events": [
            ("2016-11-16", "Emmanuel Macron annonce sa candidature", "Macron candidat", ["macron"]),
            ("2016-11-27", "François Fillon remporte la primaire de la droite", "Primaire LR", ["fillon"]),
            ("2016-12-01", "François Hollande renonce à se représenter", "Hollande renonce", []),
            ("2017-01-25", "Le Canard enchaîné révèle l'affaire des emplois de Penelope Fillon", "Affaire Fillon", ["fillon"]),
            ("2017-01-29", "Benoît Hamon remporte la primaire de la gauche", "Primaire PS", ["hamon"]),
            ("2017-02-22", "François Bayrou propose une alliance à Emmanuel Macron", "Ralliement Bayrou", ["macron"]),
            ("2017-03-14", "François Fillon mis en examen", "Fillon mis en examen", ["fillon"]),
            ("2017-03-20", "Premier débat télévisé entre cinq candidats", "1er débat", ["macron", "lepen", "fillon", "melenchon", "hamon"]),
        ],
    },
    2022: {
        "date": "2022-04-10",
        "candidates": [
            ("Emmanuel Macron", "macron", "Macron", "La République en marche", 4),
            ("Marine Le Pen", "lepen", "Le Pen", "Rassemblement national", 1),
            ("Jean-Luc Mélenchon", "melenchon", "Mélenchon", "La France insoumise", 8),
            ("Éric Zemmour", "zemmour", "Zemmour", "Reconquête", 3),
            ("Valérie Pécresse", "pecresse", "Pécresse", "Les Républicains", 7),
            ("Yannick Jadot", "jadot", "Jadot", "Europe Écologie Les Verts", 6),
            ("Jean Lassalle", "lassalle", "Lassalle", "Résistons !", 5),
            ("Fabien Roussel", "roussel", "Roussel", "Parti communiste français", 2),
        ],
        "second": {"macron": 58.55, "lepen": 41.45},
        "events": [
            ("2021-11-30", "Éric Zemmour annonce sa candidature", "Zemmour candidat", ["zemmour"]),
            ("2021-12-04", "Valérie Pécresse désignée candidate des Républicains", "Congrès LR", ["pecresse"]),
            ("2022-02-13", "Meeting de Valérie Pécresse au Zénith de Paris", "Zénith Pécresse", ["pecresse"]),
            ("2022-02-24", "La Russie envahit l'Ukraine", "Guerre en Ukraine", []),
            ("2022-03-03", "Emmanuel Macron annonce sa candidature", "Macron candidat", ["macron"]),
        ],
    },
}


def D(s: str) -> dt.date: return dt.date.fromisoformat(s)


def national_first_round(text: str) -> str:
    """The first-round part of a poll page, without its regional sections."""
    start, end = text.find("== First round =="), text.find("== Second round ==")
    body = text[start:end if end > 0 else None]
    # re.split with one group: [before first heading, title1, content1, title2, content2, ...]
    parts = HEADING.split(body)
    kept = [parts[0]]
    for title, content in zip(parts[1::2], parts[2::2]):
        if not REGIONAL.match(title):
            kept.append(content)
    return "\n".join(kept)


def standard_field(polls: list[dict], day: dt.date) -> set[str]:
    """Names tested in at least STD_SHARE of the polls of the STD_DAYS days up to `day`."""
    window = [p for p in polls if day - dt.timedelta(days=STD_DAYS) < D(p["date"]) <= day]
    count: dict[str, int] = {}
    for p in window:
        for name in {n for s in p["scenarios"] for n in s}:
            count[name] = count.get(name, 0) + 1
    return {n for n, c in count.items() if c >= STD_SHARE * len(window)}


def reference_scenario(poll: dict, field: set[str], tracked: set[str]) -> dict[str, float]:
    """app.js lineup(): most tracked candidates, minus EXTRA_PENALTY per name outside the
    standard field; ties go to fewer names, then to the first line-up of the source."""
    best, key = poll["scenarios"][0], None
    for s in poll["scenarios"]:
        score = len(tracked & set(s)) - EXTRA_PENALTY * len(set(s) - field)
        k = (score, -len(s))
        if key is None or k > key:
            best, key = s, k
    return best


def site_poll(poll: dict, ref: dict[str, float], ids: dict[str, str]) -> dict[str, Any] | None:
    """{firm, url, date, sample, n, v: {id: score}, r: {id: [lo, hi]} when line-ups differ}."""
    values = {ids[n]: v for n, v in ref.items() if n in ids}
    if not values:
        return None
    ranges = {}
    for name, cid in ids.items():
        scores = [s[name] for s in poll["scenarios"] if name in s]
        if cid in values and min(scores) < max(scores):
            ranges[cid] = [min(scores), max(scores)]
    out = {"firm": poll["firm"], "url": poll["url"], "date": poll["date"], "sample": poll["sample"],
           "n": len(poll["scenarios"]), "v": values}
    if ranges:
        out["r"] = ranges
    return out


def build_election(year: int, cfg: dict[str, Any]) -> dict[str, Any]:
    eday = D(cfg["date"])
    rows = parse(national_first_round((RAW / f"polls_{year}.txt").read_text(encoding="utf-8")), whole=True)
    results = [p for p in rows if p["firm"] == f"{year} election"]
    if not results:
        raise ValueError(f"{year}: no '{year} election' row in the poll page")
    result = max(results, key=lambda p: len(p["scenarios"][0]))["scenarios"][0]
    polls = sorted((p for p in rows if "election" not in p["firm"].lower() and D(p["date"]) < eday),
                   key=lambda p: p["date"])

    ids = {name: cid for name, cid, *_ in cfg["candidates"]}
    missing = [n for n in ids if n not in result]
    if missing:
        raise ValueError(f"{year}: {missing} not in the official result row")
    tracked = set(ids)

    out_polls = []
    for p in polls:
        ref = reference_scenario(p, standard_field(polls, D(p["date"])), tracked)
        sp = site_poll(p, ref, ids)
        if sp:
            out_polls.append(sp)

    candidates = [{"id": cid, "name": name, "short": short, "party": party, "slot": slot, "result": result[name]}
                  for name, cid, short, party, slot in cfg["candidates"]]
    others = round(sum(v for n, v in result.items() if n not in ids), 2)
    events = []
    for date, label, short, who, *end in cfg["events"]:
        e = {"date": date, "label": label, "short": short, "who": who}
        if end:
            e["end"] = end[0]
        events.append(e)
    LOGGER.info("%d: %d polls (%s to %s)", year, len(out_polls), out_polls[0]["date"], out_polls[-1]["date"])
    return {
        "year": year, "date": cfg["date"],
        "source": WIKI_FR.format(year), "polls_index": POLLS_EN.format(year),
        "candidates": candidates, "others": others, "second": cfg["second"],
        "events": events,
        "polls": out_polls,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    payload = {"elections": [build_election(y, c) for y, c in ELECTIONS.items()]}
    write_js(OUTPUT, "HISTORY", payload, header=HEADER)
    LOGGER.info("wrote %s (%d kB)", OUTPUT.relative_to(ROOT), OUTPUT.stat().st_size // 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
