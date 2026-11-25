"""Tests for scripts/build_history.py (data/history.js, the past-elections pages)."""
from __future__ import annotations

import pytest

from build_history import ELECTIONS, build_election, national_first_round, reference_scenario

PAGE = """intro
== First round ==
=== 2022 ===
{| national table |}
=== By region ===
{| regional table |}
==== By department ====
{| department table |}
=== 2021 ===
{| older national table |}
== Second round ==
{| duel table |}
"""


def test_national_first_round_drops_regional_sections() -> None:
    text = national_first_round(PAGE)
    assert "national table" in text and "older national table" in text
    assert "regional" not in text and "department" not in text and "duel" not in text


def test_reference_scenario_prefers_the_usual_field() -> None:
    # Same rule as app.js lineup(): an unusual name costs 1.5 tracked candidates.
    poll = {"scenarios": [
        {"A": 30.0, "B": 20.0, "X": 10.0, "Y": 5.0},   # 2 tracked, 2 unusual: 2 - 3 = -1
        {"A": 31.0, "C": 15.0},                        # 1 tracked, 1 unusual: 1 - 1.5 = -0.5
        {"A": 32.0, "B": 21.0, "C": 14.0},             # 2 tracked, 1 unusual: 0.5
    ]}
    assert reference_scenario(poll, field={"A", "B"}, tracked={"A", "B"}) == poll["scenarios"][2]


def test_reference_scenario_tie_goes_to_fewer_names() -> None:
    poll = {"scenarios": [{"A": 30.0, "B": 20.0, "C": 5.0}, {"A": 31.0, "B": 21.0}]}
    assert reference_scenario(poll, field={"A", "B", "C"}, tracked={"A", "B"}) == poll["scenarios"][1]


@pytest.mark.parametrize("year", sorted(ELECTIONS))
def test_real_election(year: int) -> None:
    """Built from the committed Wikipedia page: 8 candidates, national polls only, all before the vote."""
    e = build_election(year, ELECTIONS[year])
    assert len(e["candidates"]) == 8
    assert len({c["slot"] for c in e["candidates"]}) == 8      # one colour per candidate
    results = [c["result"] for c in e["candidates"]]
    assert results == sorted(results, reverse=True)            # the 8 best results, in order
    assert all(p["date"] < e["date"] for p in e["polls"])
    for p in e["polls"]:
        assert not any(k in (p["url"] or "").lower() for k in ("reunion", "corse", "paca")), p
    assert 95 < sum(results) + e["others"] < 101
