"""Tests for scripts/validate_data.py.

Each test writes small, hand-made data files into a temporary folder (not the real
data/, which changes twice a week) and runs the validator on it.
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from validate_data import FILES, validate

DAY = "2026-11-12"
URL = "https://example.org/source"

# The smallest payload of each file that passes validation, keyed by JS variable.
VALID: dict[str, Any] = {
    "POLLS": {
        "fetched": DAY,
        "polls": [{
            "firm": "Ifop", "url": URL, "start": "2026-11-10", "date": DAY, "sample": 1000,
            "scenarios": [{"lepen":25.0, "melenchon": 75.0}],
        }],
    },
    "MODEL": {
        "asof": DAY, "election": "2027-04-18", "n_polls": 3,
        "candidates": [{"id": "melenchon", "name": "Jean-Luc Mélenchon", "base": 31.0}],
        "duels": {}, "sigma_first": {"30": 5.57},
    },
    "SOCIAL": {
        "updated": DAY,
        "followers": {"melenchon": {"x": {"points": [{"date": DAY, "value": 3_000_000, "source": URL}]}}},
        "members": {"melenchon": {"points": [{"date": DAY, "value": 112_319, "source": URL}]}},
    },
    "ENGAGEMENT": {
        "updated": DAY,
        "candidates": {"melenchon": {"history": [
            {"date": DAY, "rate": 2.5, "posts": [{"url": "https://www.instagram.com/p/abc/"}]},
        ]}},
    },
}

DELETE = object()  # set_path value meaning "remove this key"


def set_path(payloads: dict[str, Any], path: str, value: Any) -> None:
    """set_path(p, "POLLS.polls.0.sample", 0) is p["POLLS"]["polls"][0]["sample"] = 0."""
    *parents, last = path.split(".")
    node: Any = payloads
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    last_key: Any = int(last) if isinstance(node, list) else last
    if value is DELETE:
        del node[last_key]
    else:
        node[last_key] = value


def write(root: Path, payloads: dict[str, Any]) -> None:
    for name, (variable, _model) in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"window.{variable} = {json.dumps(payloads[variable])};\n", encoding="utf-8")


@pytest.fixture
def payloads() -> dict[str, Any]:
    return copy.deepcopy(VALID)


def test_valid_data_passes(tmp_path: Path, payloads: dict[str, Any]) -> None:
    write(tmp_path, payloads)
    validate(tmp_path)


@pytest.mark.parametrize(("path", "value", "error_type"), [
    # Security: links are rendered in href attributes.
    ("POLLS.polls.0.url", "javascript:alert(1)", "url_scheme"),
    # Has a host, so only the scheme check stops it (%0A ends the "//" comment in JS).
    ("SOCIAL.followers.melenchon.x.points.0.source", "javascript://example.org/%0Aalert(1)", "url_scheme"),
    ("POLLS.polls.0.url", "", "url_parsing"),
    # Strict types: no silent coercion.
    ("POLLS.polls.0.sample", True, "int_type"),
    ("POLLS.polls.0.sample", "1000", "int_type"),
    ("POLLS.polls.0.date", "12/11/2026", "date_parsing"),
    ("POLLS.polls.0.firm", DELETE, "missing"),
    # Ranges and business rules.
    ("POLLS.polls", [], "too_short"),
    ("POLLS.polls.0.sample", 0, "greater_than"),
    ("POLLS.polls.0.scenarios.0.melenchon", 120.0, "less_than_equal"),
    ("POLLS.polls.0.scenarios.0", {"melenchon": 70.0, "lepen": 50.0}, "value_error"),
    ("MODEL.sigma_first.30", -1.0, "greater_than"),
    ("MODEL.candidates", [], "too_short"),
    ("SOCIAL.members.melenchon.points.0.value", -5, "greater_than"),
    ("ENGAGEMENT.candidates.melenchon.history.0.rate", 150.0, "less_than"),
    ("ENGAGEMENT.candidates.melenchon.history.0.posts.0.url", "https://example.org/SAMPLE", "value_error"),
])
def test_invalid_value_is_rejected(tmp_path: Path, payloads: dict[str, Any],
                                   path: str, value: Any, error_type: str) -> None:
    set_path(payloads, path, value)
    write(tmp_path, payloads)
    with pytest.raises(ValidationError) as exc:
        validate(tmp_path)
    errors = exc.value.errors()
    assert len(errors) == 1, errors
    assert errors[0]["type"] == error_type


def test_every_error_of_a_file_is_reported(tmp_path: Path, payloads: dict[str, Any]) -> None:
    set_path(payloads, "POLLS.polls.0.url", "javascript:alert(1)")
    set_path(payloads, "POLLS.polls.0.sample", True)
    write(tmp_path, payloads)
    with pytest.raises(ValidationError) as exc:
        validate(tmp_path)
    assert {e["loc"] for e in exc.value.errors()} == {("polls", 0, "url"), ("polls", 0, "sample")}


def test_missing_assignment_is_rejected(tmp_path: Path, payloads: dict[str, Any]) -> None:
    write(tmp_path, payloads)
    (tmp_path / "data/model.js").write_text("var MODEL = {};", encoding="utf-8")
    with pytest.raises(ValueError, match="window.MODEL ="):
        validate(tmp_path)


def test_malformed_json_is_rejected(tmp_path: Path, payloads: dict[str, Any]) -> None:
    write(tmp_path, payloads)
    (tmp_path / "data/engagement.js").write_text("window.ENGAGEMENT = {not json;", encoding="utf-8")
    with pytest.raises(ValidationError, match="json_invalid"):
        validate(tmp_path)


def test_missing_file_is_rejected(tmp_path: Path, payloads: dict[str, Any]) -> None:
    write(tmp_path, payloads)
    (tmp_path / "data/social.js").unlink()
    with pytest.raises(FileNotFoundError):
        validate(tmp_path)


@pytest.mark.parametrize(("path", "value", "message"), [
    ("POLLS.polls.0.start", "2026-11-20", "fieldwork starts after it ends"),
    ("MODEL.n_polls", 0, "No 2027 poll in the last 21 days"),
])
def test_warnings_do_not_fail(tmp_path: Path, payloads: dict[str, Any], caplog: pytest.LogCaptureFixture,
                              path: str, value: Any, message: str) -> None:
    set_path(payloads, path, value)
    write(tmp_path, payloads)
    with caplog.at_level(logging.WARNING):
        validate(tmp_path)
    assert message in caplog.text
