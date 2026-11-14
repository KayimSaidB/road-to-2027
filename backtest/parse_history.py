#!/usr/bin/env python3
"""Parse opinion-poll tables of French presidential elections from Wikipedia wikitext.

    python3 backtest/parse_history.py backtest/raw/polls_2022.txt backtest/data/polls_2022.json

Output: [{firm, url, date, sample, scenarios: [{"Candidate Name": pct, ...}, ...]}, ...]

A wikitext table looks like this:

    {| class="wikitable"
    ! Polling firm !! Fieldwork date !! Sample size !! [[Candidate A]] !! [[Candidate B]]
    |-
    | rowspan="2" | [https://… Ifop] || rowspan="2" | 10–12 Nov 2026 || rowspan="2" | 1,000 || 31% || 15%
    |-
    | 30% || 16%
    |}

Header cells give each column a role (firm, date, sample, candidate…). A cell spanning several
rows (rowspan) is repeated in the rows below: consecutive rows sharing firm, date and sample are
the scenarios (hypotheses) of one poll.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import NamedTuple

LOGGER = logging.getLogger("parse_history")

MONTHS = "january february march april may june july august september october november december".split()

TABLE_RE = re.compile(r"\{\|.*?\n\|\}", re.S)
ROW_SEPARATOR_RE = re.compile(r"\n\|-[^\n]*")
COLSPAN_RE = re.compile(r'colspan\s*=\s*"?(\d+)')
ROWSPAN_RE = re.compile(r'rowspan\s*=\s*"?(\d+)')
LEADING_ROWSPAN_RE = re.compile(r'\s*(rowspan\s*=\s*"?\d+"?)\s*(.*)', re.S)
HTML_ATTRIBUTE_RE = re.compile(r"\w+\s*=")
# Everything from a footnote or a template to the end of the line: "1,000<ref>…" -> "1,000".
REF_OR_TEMPLATE_TAIL_RE = re.compile(r"<ref.*|\{\{.*")

ISO_SORT_KEY_RE = re.compile(r'data-sort-value\s*=\s*"?(\d{4})-(\d{2})-(\d{2})')
OPDRTS_TEMPLATE_RE = re.compile(r"\{\{Opdrts\|([^}]*)\}\}")  # {{Opdrts|10|12|Nov|2026|year}}
TAG_OR_TEMPLATE_RE = re.compile(r"<[^>]+>|\{\{[^}]*\}\}")
DAY_MONTH_YEAR_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})")

EXTERNAL_LINK_RE = re.compile(r"\[(https?://\S+)\s+([^\]]+)\]")  # [https://… Ifop]
WIKI_LINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")      # [[Ifop]] or [[Ifop|label]]
FIRM_MARKUP_RE = re.compile(r"<[^>]+>|'''|\{\{[^}]*\}\}")
LINK_TARGET_RE = re.compile(r"\[\[([^\]|]+)")

FOOTNOTE_OR_COMMENT_RE = re.compile(r"<ref.*?(</ref>|/>)|<!--.*?-->", re.S)
BELOW_HALF_RE = re.compile(r"<\s*0[.,]5")
PERCENTAGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
BELOW_HALF_VALUE = 0.25  # "<0.5%" is counted as 0.25 %

NOTE_ROW_MIN_COLSPAN = 4  # a cell this wide is a timeline note ("Le Pen announces…"), not a poll


# ---------- data types ----------

class Role(Enum):
    FIRM = "firm"
    DATE = "date"
    SAMPLE = "sample"
    ABSTENTION = "abstention"
    CANDIDATE = "candidate"
    OTHER = "other"


@dataclass(frozen=True)
class Column:
    role: Role
    label: str = ""  # candidate name for CANDIDATE, raw header text for OTHER


class Cell(NamedTuple):
    attributes: str  # e.g. 'rowspan="2" style="…"', empty when none
    text: str


@dataclass
class Poll:
    firm: str
    url: str | None
    date: str
    sample: int | None
    scenarios: list[dict[str, float]] = field(default_factory=list)


@dataclass
class _Carried:
    """A rowspan cell still to be repeated in the next `remaining` rows."""
    remaining: int
    cell: Cell


# ---------- cells ----------

def span(attributes: str, pattern: re.Pattern[str]) -> int:
    match = pattern.search(attributes)
    return int(match.group(1)) if match else 1


def split_cell_attributes(cell: str) -> Cell:
    """'rowspan="2" | 31%' -> Cell('rowspan="2" ', ' 31%'). Pipes inside [[…]], [ ] or {{…}} are content."""
    depth, pos = 0, 0
    while pos < len(cell):
        pair = cell[pos:pos + 2]
        if pair in ("[[", "{{"):
            depth += 1
            pos += 2
            continue
        if pair in ("]]", "}}"):
            depth -= 1
            pos += 2
            continue
        char = cell[pos]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif char == "|" and depth == 0:
            before = cell[:pos]
            # Only attributes if it looks like HTML attributes (or is empty).
            if HTML_ATTRIBUTE_RE.search(before) or not before.strip():
                return Cell(before, cell[pos + 1:])
            return Cell("", cell)
        pos += 1
    return Cell("", cell)


def month_number(name: str) -> int:
    """'Nov', 'november', 'Nov.' -> 11."""
    prefix = name.strip().lower().rstrip(".")[:3]
    for number, month in enumerate(MONTHS, start=1):
        if month.startswith(prefix):
            return number
    raise ValueError(f"unknown month {name!r}")


def parse_date(cell: Cell) -> str | None:
    """End of fieldwork as YYYY-MM-DD, from a sort key, an {{Opdrts}} template or plain text."""
    sort_key = ISO_SORT_KEY_RE.search(cell.attributes + " " + cell.text)
    if sort_key:
        return "-".join(sort_key.groups())

    template = OPDRTS_TEMPLATE_RE.search(cell.text)
    if template:
        parts = [part.strip() for part in template.group(1).split("|")]
        numbers = [part for part in parts if part.isdigit()]
        year = next(n for n in numbers if len(n) == 4)
        month_names = [part for part in parts if part and not part.isdigit() and part != "year"]
        days = [n for n in numbers if len(n) <= 2]
        return f"{int(year):04d}-{month_number(month_names[-1]):02d}-{int(days[-1]):02d}"

    found = DAY_MONTH_YEAR_RE.findall(TAG_OR_TEMPLATE_RE.sub(" ", cell.text))
    if not found:
        return None
    day, month, year = found[-1]  # "10–12 Nov 2026": the last date is the end of fieldwork
    try:
        return f"{int(year):04d}-{month_number(month):02d}-{int(day):02d}"
    except ValueError:
        return None


def parse_firm(text: str) -> tuple[str, str | None]:
    """Polling firm name and the link to its publication, if any."""
    external = EXTERNAL_LINK_RE.search(text)
    if external:
        return FIRM_MARKUP_RE.sub("", external.group(2)).strip(), external.group(1)
    wiki = WIKI_LINK_RE.search(text)
    name = wiki.group(1) if wiki else REF_OR_TEMPLATE_TAIL_RE.sub("", text)
    return name.strip(), None


def parse_sample(text: str) -> int | None:
    """'1,000<ref>…</ref>' -> 1000."""
    digits = re.sub(r"\D", "", REF_OR_TEMPLATE_TAIL_RE.sub("", text))
    return int(digits) if digits else None


def parse_percentage(text: str) -> float | None:
    text = FOOTNOTE_OR_COMMENT_RE.sub("", text)
    if BELOW_HALF_RE.search(text) or "&lt;0.5" in text:
        return BELOW_HALF_VALUE
    match = PERCENTAGE_RE.search(text)
    return float(match.group(1).replace(",", ".")) if match else None


# ---------- header ----------

def header_rows(table: str) -> list[list[str]]:
    """Cells of each header row (lines starting with !), up to the first data row."""
    rows: list[list[str]] = []
    current: list[str] = []
    for line in table.split("\n")[1:]:
        if line.startswith("|-"):
            if current:
                rows.append(current)
                current = []
            continue
        if line.startswith("!"):
            current += line[1:].split("!!")
        elif line.startswith("|") and current:
            break  # first data row reached
    if current:
        rows.append(current)
    return rows


def header_column(cell: str) -> tuple[Column, int]:
    """Role of a header cell and how many columns it spans."""
    attributes, text = split_cell_attributes(cell)
    lower = text.lower()
    start = lower.strip()
    if "polling" in lower or "firm" in lower:
        column = Column(Role.FIRM)
    elif "fieldwork" in lower or start.startswith("date"):
        column = Column(Role.DATE)
    elif "sample" in lower:
        column = Column(Role.SAMPLE)
    elif "abstention" in lower or start.startswith("abs"):
        column = Column(Role.ABSTENTION)
    else:
        links = [t for t in LINK_TARGET_RE.findall(text) if not t.lower().startswith(("file:", "image:"))]
        column = Column(Role.CANDIDATE, links[0].strip()) if links else Column(Role.OTHER, text.strip())
    return column, span(attributes, COLSPAN_RE)


def header_columns(table: str) -> list[Column]:
    """One Column per table column. Photo-only header cells take their name from a later header row."""
    rows = header_rows(table)
    if not rows:
        return []
    columns: list[Column] = []
    for cell in rows[0]:
        column, width = header_column(cell)
        columns += [column] * width

    unnamed = [i for i, column in enumerate(columns) if column.role is Role.OTHER]
    for row in rows[1:]:
        names = [column for column, _ in map(header_column, row) if column.role is Role.CANDIDATE]
        if unnamed and names and len(names) == len(unnamed):
            for i, column in zip(unnamed, names):
                columns[i] = column
            break
    return columns


def find(columns: list[Column], role: Role) -> int | None:
    return next((i for i, column in enumerate(columns) if column.role is role), None)


# ---------- rows ----------

def row_cells(row: str) -> list[Cell]:
    """Cells of one data row, written on one line (a || b) or one per line."""
    cells = []
    for line in row.split("\n"):
        if not line.startswith("|") or line.startswith(("|}", "{|")):
            continue
        for raw in line[1:].split("||"):
            attributes, text = split_cell_attributes(raw)
            if not attributes:
                # 'rowspan="2" 31%' without the pipe separator.
                leading = LEADING_ROWSPAN_RE.match(text)
                if leading:
                    attributes, text = leading.groups()
            cells.append(Cell(attributes, text.strip()))
    return cells


def is_note_row(cells: list[Cell]) -> bool:
    return any(span(cell.attributes, COLSPAN_RE) >= NOTE_ROW_MIN_COLSPAN for cell in cells)


def place_cells(cells: list[Cell], width: int, carried: dict[int, _Carried]) -> list[Cell | None]:
    """Put each cell in its column(s), filling columns still covered by a rowspan from above.

    Updates `carried` with the rowspan cells of this row, for the rows below.
    """
    placed: list[Cell | None] = [None] * width
    remaining_cells = iter(cells)
    col = 0
    while col < width:
        above = carried.get(col)
        if above and above.remaining > 0:
            placed[col] = above.cell
            above.remaining -= 1
            col += 1
            continue
        cell = next(remaining_cells, None)
        if cell is None:
            break
        colspan = span(cell.attributes, COLSPAN_RE)
        rowspan = span(cell.attributes, ROWSPAN_RE)
        for offset in range(colspan):
            if col + offset < width:
                placed[col + offset] = cell
                if rowspan > 1:
                    carried[col + offset] = _Carried(rowspan - 1, cell)
        col += colspan
    return placed


def scores(columns: list[Column], placed: list[Cell | None]) -> dict[str, float]:
    result = {}
    for column, cell in zip(columns, placed):
        if column.role is Role.CANDIDATE and cell:
            value = parse_percentage(cell.text)
            if value is not None:
                result[column.label] = value
    return result


def parse_table(table: str, min_candidates: int) -> list[Poll]:
    columns = header_columns(table)
    firm_col, date_col, sample_col = (find(columns, r) for r in (Role.FIRM, Role.DATE, Role.SAMPLE))
    if firm_col is None or date_col is None:
        return []

    polls: list[Poll] = []
    carried: dict[int, _Carried] = {}
    for row in ROW_SEPARATOR_RE.split(table)[1:]:
        cells = row_cells(row)
        if not cells or is_note_row(cells):
            continue
        placed = place_cells(cells, len(columns), carried)
        firm_cell, date_cell = placed[firm_col], placed[date_col]
        if not firm_cell or not date_cell:
            continue
        date = parse_date(date_cell)
        if not date:
            continue
        firm, url = parse_firm(firm_cell.text)
        sample_cell = placed[sample_col] if sample_col is not None else None
        sample = parse_sample(sample_cell.text) if sample_cell else None
        scenario = scores(columns, placed)
        if len(scenario) < min_candidates:
            continue

        previous = polls[-1] if polls else None
        if previous and (previous.firm, previous.date, previous.sample) == (firm, date, sample):
            previous.scenarios.append(scenario)  # another hypothesis of the same poll
        else:
            polls.append(Poll(firm, url, date, sample, [scenario]))
    return polls


# ---------- entry points ----------

def parse(text: str, min_vals: int = 3, whole: bool = False) -> list[dict]:
    """Polls of the first-round tables of a Wikipedia poll page, as dicts.

    min_vals: rows with fewer candidate scores are skipped (2 for second-round duels).
    whole: parse every table in `text` (e.g. one duel section), not only the first round.
    """
    if whole:
        body = text
    else:
        start = text.find("== First round ==")
        end = text.find("== Second round ==")
        body = text[start:end if end > 0 else None]
    return [asdict(poll) for table in TABLE_RE.findall(body) for poll in parse_table(table, min_vals)]


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(argv) != 2:
        LOGGER.error("usage: parse_history.py <wikitext.txt> <output.json>")
        return 2
    source, output = map(Path, argv)
    polls = parse(source.read_text(encoding="utf-8"))
    output.write_text(json.dumps(polls, ensure_ascii=False, indent=0), encoding="utf-8")
    if polls:
        dates = [poll["date"] for poll in polls]
        LOGGER.info("%s -> %d polls %s %s", source, len(polls), min(dates), max(dates))
    else:
        LOGGER.warning("%s -> no poll found", source)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
