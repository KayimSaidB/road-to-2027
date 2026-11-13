#!/usr/bin/env python3
"""Validate the data files the site loads (data/*.js) before they are committed or deployed.

Each file is parsed into a pydantic model: wrong types, missing fields, out-of-range
values or unsafe links raise a ValidationError listing every problem of that file.
Stops at the first invalid file, exit code 1.

    python3 scripts/validate_data.py
"""
from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path
from typing import Annotated, Any

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, NonNegativeInt,
                      PositiveFloat, PositiveInt, ValidationError, model_validator)

ROOT = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger("validate_data")


class Strict(BaseModel):
    # strict: no silent coercion ("12" or true is not an int). Extra fields are ignored:
    # only what the site relies on is declared.
    model_config = ConfigDict(strict=True)


Score = Annotated[float, Field(ge=0, le=100)]
# HttpUrl only accepts http(s) links with a host: a javascript: URL in an href would
# run code in the visitor's browser.
Link = HttpUrl


# ---------- data/polls.js ----------

def _total_at_most_100(scenario: dict[str, float]) -> dict[str, float]:
    # Tracked candidates only, so at most 100 (+ rounding).
    if sum(scenario.values()) > 101:
        raise ValueError(f"scores add up to {sum(scenario.values()):g} %")
    return scenario


class Poll(Strict):
    firm: str
    url: Link
    start: dt.date
    date: dt.date
    sample: PositiveInt
    scenarios: list[Annotated[dict[str, Score], AfterValidator(_total_at_most_100)]] = Field(min_length=1)

    @model_validator(mode="after")
    def _dates(self) -> Poll:
        if self.start > self.date:
            LOGGER.warning("%s %s: fieldwork starts after it ends (%s)", self.firm, self.date, self.start)
        return self


class Polls(Strict):
    fetched: dt.date
    polls: list[Poll] = Field(min_length=1)


# ---------- data/model.js ----------

class ModelCandidate(Strict):
    id: str
    name: str
    base: float


class SimulatorModel(Strict):
    asof: dt.date
    election: dt.date
    n_polls: NonNegativeInt
    candidates: list[ModelCandidate] = Field(min_length=1)
    duels: dict[str, Any]
    sigma_first: dict[str, PositiveFloat] = Field(min_length=1)

    @model_validator(mode="after")
    def _recent_polls(self) -> SimulatorModel:
        if self.n_polls == 0:
            LOGGER.warning("No 2027 poll in the last 21 days: simulator base unchanged")
        return self


# ---------- data/social.js ----------

class Point(Strict):
    date: dt.date
    value: PositiveInt
    source: Link


class Account(Strict):
    points: list[Point]


class Social(Strict):
    updated: dt.date
    followers: dict[str, dict[str, Account]]  # candidate -> network -> account
    members: dict[str, Account]               # candidate -> party members


# ---------- data/engagement.js ----------

def _not_sample(url: HttpUrl) -> HttpUrl:
    if "SAMPLE" in str(url):
        raise ValueError("sample fixture data leaked into data/")
    return url


class Post(Strict):
    url: Annotated[Link, AfterValidator(_not_sample)]


class EngagementEntry(Strict):
    date: dt.date
    rate: Annotated[float, Field(ge=0, lt=100)] | None = None
    posts: list[Post] = []


class EngagementAccount(Strict):
    history: list[EngagementEntry] = []


class Engagement(Strict):
    updated: dt.date
    candidates: dict[str, EngagementAccount]


# ---------- runner ----------

# file -> (JS variable it assigns, model)
FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "data/polls.js": ("POLLS", Polls),
    "data/model.js": ("MODEL", SimulatorModel),
    "data/social.js": ("SOCIAL", Social),
    "data/engagement.js": ("ENGAGEMENT", Engagement),
}


def load_json(path: Path, variable: str) -> str:
    """Return the JSON text of `window.<variable> = {...};`."""
    text = path.read_text(encoding="utf-8")
    prefix = f"window.{variable} = "
    if prefix not in text:
        raise ValueError(f"{path}: '{prefix.strip()}' not found")
    return text.split(prefix, 1)[1].rsplit(";", 1)[0]


def validate(root: Path = ROOT) -> None:
    """Raise ValueError (ValidationError is one) at the first invalid file."""
    for name, (variable, model) in FILES.items():
        model.model_validate_json(load_json(root / name, variable))
        LOGGER.info("%s: ok", name)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        validate()
    except (OSError, ValueError) as exc:  # ValidationError and JSON errors are ValueErrors
        LOGGER.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
