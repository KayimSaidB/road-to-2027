"""Tests for scripts/update_polls.py: what the site keeps from the parsed polls.

Reading the Wikipedia tables is tested in test_wikitext.py.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from road2027.wikitext import Poll
from update_polls import SINCE, build_payload, main, to_site_poll
from validate_data import Polls

RAW_2027 = Path(__file__).resolve().parent.parent / "backtest/raw/polls_2027.txt"


def poll(firm: str = "Ifop", date: str = "2026-11-12", scenarios: list[dict[str, float]] | None = None) -> Poll:
    return Poll(firm, "https://example.org/poll", "2026-11-10", date, 1000,
                scenarios if scenarios is not None else [{"Marine Le Pen": 31.0, "Éric Zemmour": 4.0}])


def test_site_poll_splits_tracked_and_other_candidates() -> None:
    assert to_site_poll(poll()) == {
        "firm": "Ifop", "url": "https://example.org/poll", "start": "2026-11-10", "date": "2026-11-12",
        "sample": 1000, "scenarios": [{"lepen": 31.0}], "others": [{"Éric Zemmour": 4.0}],
    }


def test_scenarios_and_others_stay_aligned() -> None:
    site = to_site_poll(poll(scenarios=[{"Marine Le Pen": 31.0}, {"Éric Zemmour": 5.0, "Marine Le Pen": 30.0}]))
    assert site is not None
    assert site["scenarios"] == [{"lepen": 31.0}, {"lepen": 30.0}]
    assert site["others"] == [{}, {"Éric Zemmour": 5.0}]


def test_poll_before_since_is_dropped() -> None:
    assert to_site_poll(poll(date="2024-06-30")) is None
    assert to_site_poll(poll(date=SINCE)) is not None


def test_poll_without_tracked_candidate_is_dropped() -> None:
    assert to_site_poll(poll(scenarios=[{"Éric Zemmour": 4.0, "Bruno Retailleau": 6.0}])) is None


def test_payload_sorted_by_date_then_firm() -> None:
    polls = [poll("Ifop", "2026-11-12"), poll("Elabe", "2026-11-12"), poll("Odoxa", "2026-10-01")]
    payload = build_payload(polls, dt.date(2026, 11, 14))
    assert [(p["firm"], p["date"]) for p in payload["polls"]] == [
        ("Odoxa", "2026-10-01"), ("Elabe", "2026-11-12"), ("Ifop", "2026-11-12"),
    ]
    assert payload["fetched"] == "2026-11-14"


def test_real_page_produces_valid_site_data(tmp_path: Path) -> None:
    """End to end on the committed Wikipedia page: the output passes data/polls.js validation."""
    out = tmp_path / "polls.js"
    assert main([str(RAW_2027), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("/* Généré par scripts/update_polls.py")
    payload = Polls.model_validate_json(text.split("window.POLLS = ", 1)[1].rsplit(";", 1)[0])
    assert payload.polls  # the page changes with every bot update: no exact count
    assert all(p.start is not None and p.start <= p.date for p in payload.polls)
