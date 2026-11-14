"""Tests for road2027.wikitext (src/road2027/wikitext.py).

Three levels: the small cell parsers, whole hand-written tables, and the real Wikipedia
pages (backtest/raw) against the JSON committed next to them (backtest/data).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from road2027.wikitext import (Cell, Column, Role, header_column, header_columns, month_number, parse,
                           parse_date, parse_firm, parse_percentage, parse_sample, parse_start,
                           split_cell_attributes)

ROOT = Path(__file__).resolve().parent.parent


# ---------- cells ----------

@pytest.mark.parametrize(("cell", "expected"), [
    (Cell('data-sort-value="2026-11-12"', "10–12 Nov 2026"), "2026-11-12"),  # sort key wins
    (Cell("", "{{Opdrts|10|12|Nov|2026|year}}"), "2026-11-12"),
    (Cell("", "10–12 Nov 2026"), "2026-11-12"),                             # end of fieldwork
    (Cell("", "28 Oct – 2 Nov. 2026"), "2026-11-02"),
    (Cell("", "3 November 2026<ref>source</ref>"), "2026-11-03"),
    (Cell("", "late 2026"), None),
    (Cell("", "10 Foo 2026"), None),                                         # unknown month
])
def test_parse_date(cell: Cell, expected: str | None) -> None:
    assert parse_date(cell) == expected


@pytest.mark.parametrize(("text", "end", "expected"), [
    ("{{Opdrts|10|12|Nov|2026|year}}", "2026-11-12", "2026-11-10"),
    ("{{Opdrts||12|Nov|2026|year}}", "2026-11-12", "2026-11-12"),     # one-day fieldwork
    ("{{Opdrts|28|Oct|2|Nov|2026}}", "2026-11-02", "2026-10-28"),     # spelled-out first month
    ("{{Opdrts|31|1|Sep|2026|year}}", "2026-09-01", "2026-08-31"),    # first day > last: month before
    ("{{Opdrts|30|2|Jan|2027|year}}", "2027-01-02", "2026-12-30"),    # ... and year before
    ("10–12 Nov 2026", "2026-11-12", None),                           # only from the template
])
def test_parse_start(text: str, end: str, expected: str | None) -> None:
    assert parse_start(Cell("", text), end) == expected


@pytest.mark.parametrize("name", ["Nov", "nov.", "November", " NOVEMBER "])
def test_month_number(name: str) -> None:
    assert month_number(name) == 11


def test_month_number_rejects_unknown_month() -> None:
    with pytest.raises(ValueError, match="unknown month"):
        month_number("Foo")


@pytest.mark.parametrize(("text", "expected"), [
    ("31%", 31.0),
    ("12,5 %", 12.5),
    ("<0.5%", 0.25),
    ("&lt;0.5%", 0.25),
    ("31%<ref>up 5% since May</ref>", 31.0),  # numbers in footnotes are ignored
    ("<!-- 9% --> 8%", 8.0),
    ("–", None),
])
def test_parse_percentage(text: str, expected: float | None) -> None:
    assert parse_percentage(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("[https://example.org/ifop Ifop]", ("Ifop", "https://example.org/ifop")),
    ("[https://example.org/ifop '''Ifop-Fiducial''']", ("Ifop-Fiducial", "https://example.org/ifop")),
    ("[[Elabe]]", ("Elabe", None)),
    ("[[Ifop-Fiducial|Ifop]]", ("Ifop", None)),
    ("Harris Interactive<ref>source</ref>", ("Harris Interactive", None)),
])
def test_parse_firm(text: str, expected: tuple[str, str | None]) -> None:
    assert parse_firm(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("1,000", 1000),
    ("1 500<ref>online panel of 2,000</ref>", 1500),
    ("–", None),
])
def test_parse_sample(text: str, expected: int | None) -> None:
    assert parse_sample(text) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ('rowspan="2" | 31%', Cell('rowspan="2" ', " 31%")),
    (" | 31%", Cell(" ", " 31%")),                                  # empty attributes
    ("[[Ifop-Fiducial|Ifop]]", Cell("", "[[Ifop-Fiducial|Ifop]]")),  # pipe inside a link
    ("{{Opdrts|10|12|Nov|2026}}", Cell("", "{{Opdrts|10|12|Nov|2026}}")),
    ("Ifop | Fiducial", Cell("", "Ifop | Fiducial")),               # not attributes
])
def test_split_cell_attributes(raw: str, expected: Cell) -> None:
    assert split_cell_attributes(raw) == expected


# ---------- header ----------

@pytest.mark.parametrize(("cell", "expected"), [
    ("Polling firm", (Column(Role.FIRM), 1)),
    ("Fieldwork date", (Column(Role.DATE), 1)),
    ("Sample size", (Column(Role.SAMPLE), 1)),
    ("Abs.", (Column(Role.ABSTENTION), 1)),
    ('colspan="2" | [[Marine Le Pen]]', (Column(Role.CANDIDATE, "Marine Le Pen"), 2)),
    ("[[File:Le Pen.jpg|50px]]", (Column(Role.OTHER, "[[File:Le Pen.jpg|50px]]"), 1)),
    ("Others", (Column(Role.OTHER, "Others"), 1)),
])
def test_header_column(cell: str, expected: tuple[Column, int]) -> None:
    assert header_column(cell) == expected


PHOTO_HEADER_TABLE = """{| class="wikitable"
! rowspan="2" | Polling firm !! rowspan="2" | Fieldwork date !! [[File:A.jpg|50px]] !! [[File:B.jpg|50px]]
|-
! [[Marine Le Pen]] !! [[Jean-Luc Mélenchon]]
|-
| Ifop || 12 Nov 2026 || 31% || 15%
|}"""


def test_photo_only_header_takes_names_from_next_row() -> None:
    assert header_columns(PHOTO_HEADER_TABLE) == [
        Column(Role.FIRM), Column(Role.DATE),
        Column(Role.CANDIDATE, "Marine Le Pen"), Column(Role.CANDIDATE, "Jean-Luc Mélenchon"),
    ]


# ---------- whole tables ----------

FIRST_ROUND_TABLE = """{| class="wikitable"
! Polling firm !! Fieldwork date !! Sample size !! [[Marine Le Pen]] !! [[Jean-Luc Mélenchon]] !! [[Édouard Philippe]]
|-
| rowspan="2" | [https://example.org/ifop Ifop] || rowspan="2" | 10–12 Nov 2026 || rowspan="2" | 1,000 || 31% || 15% || 12%
|-
| 32% || 16% || 11%
|-
| colspan="6" | Philippe announces his candidacy
|-
| [[Elabe]] || {{Opdrts|3|5|Nov|2026|year}} || 1 500 || 30% || 14% || <0.5%
|-
| [[Odoxa]] || 1 Nov 2026 || 900 || 29% || – || –
|}"""


def test_parse_table() -> None:
    text = f"== First round ==\n{FIRST_ROUND_TABLE}\n"
    assert parse(text) == [
        {"firm": "Ifop", "url": "https://example.org/ifop", "start": None, "date": "2026-11-12", "sample": 1000,
         "scenarios": [  # rowspan cells repeat: two hypotheses of the same poll
             {"Marine Le Pen": 31.0, "Jean-Luc Mélenchon": 15.0, "Édouard Philippe": 12.0},
             {"Marine Le Pen": 32.0, "Jean-Luc Mélenchon": 16.0, "Édouard Philippe": 11.0},
         ]},
        # The note row (colspan 6) is skipped; Odoxa has 1 score < min_vals=3, skipped too.
        {"firm": "Elabe", "url": None, "start": "2026-11-03", "date": "2026-11-05", "sample": 1500,
         "scenarios": [{"Marine Le Pen": 30.0, "Jean-Luc Mélenchon": 14.0, "Édouard Philippe": 0.25}]},
    ]


def test_min_vals() -> None:
    text = f"== First round ==\n{FIRST_ROUND_TABLE}\n"
    assert [poll["firm"] for poll in parse(text, min_vals=1)] == ["Ifop", "Elabe", "Odoxa"]


def test_only_first_round_section_by_default() -> None:
    text = f"== First round ==\n{FIRST_ROUND_TABLE}\n== Second round ==\n{PHOTO_HEADER_TABLE}\n"
    assert [poll["firm"] for poll in parse(text, min_vals=2)] == ["Ifop", "Elabe"]
    # whole=True also reads the second table. Its Ifop poll has the same firm and date as the
    # first one, but polls are never merged across tables.
    assert [poll["firm"] for poll in parse(text, min_vals=2, whole=True)] == ["Ifop", "Elabe", "Ifop"]


def test_table_without_firm_or_date_column_is_ignored() -> None:
    table = "{|\n! Candidate !! [[Marine Le Pen]]\n|-\n| x || 31%\n|}"
    assert parse(table, min_vals=1, whole=True) == []


# ---------- real Wikipedia pages ----------

@pytest.mark.parametrize("year", [2002, 2007, 2012, 2017, 2022, 2027])
def test_real_page_matches_committed_json(year: int) -> None:
    """backtest/data/polls_<year>.json is generated from backtest/raw/polls_<year>.txt.

    Fails if a parser change alters the output (regenerate on purpose, then review the diff),
    or if the raw page and its JSON were not committed together.
    """
    raw = (ROOT / f"backtest/raw/polls_{year}.txt").read_text(encoding="utf-8")
    committed = json.loads((ROOT / f"backtest/data/polls_{year}.json").read_text(encoding="utf-8"))
    assert parse(raw) == committed
