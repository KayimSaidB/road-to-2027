"""Tests for road2027.jsdata: the data/*.js file format."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from road2027.jsdata import MissingVariableError, read_js, split_js, write_js

ROOT = Path(__file__).resolve().parent.parent


def test_split_js() -> None:
    assert split_js('/* note */\nwindow.X = {"a": 1};\n', "X") == ("/* note */\n", '{"a": 1}')


def test_split_js_keeps_semicolons_inside_the_data() -> None:
    assert split_js('window.X = {"a": "b;c"};\n', "X") == ("", '{"a": "b;c"}')


def test_missing_variable() -> None:
    with pytest.raises(MissingVariableError, match="window.Y ="):
        split_js("window.X = {};", "Y")


def test_corrupt_json_is_not_a_missing_variable(tmp_path: Path) -> None:
    """Callers may treat a missing variable as "first run": a corrupt file must still fail."""
    path = tmp_path / "x.js"
    path.write_text("window.X = {not json};", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_js(path, "X")


@pytest.mark.parametrize("indent", [None, 1])
def test_write_then_read(tmp_path: Path, indent: int | None) -> None:
    data = {"name": "Mélenchon", "values": [1, 2.5], "none": None}
    path = tmp_path / "x.js"
    write_js(path, "X", data, header="/* header */\n", indent=indent)
    assert read_js(path, "X") == data
    text = path.read_text(encoding="utf-8")
    assert text.startswith("/* header */\nwindow.X = ") and text.endswith(";\n")
    assert "Mélenchon" in text  # not escaped as é


@pytest.mark.parametrize(("name", "variable", "indent"), [
    ("data/polls.js", "POLLS", None),
    ("data/model.js", "MODEL", None),
    ("data/social.js", "SOCIAL", 1),
    ("data/engagement.js", "ENGAGEMENT", 1),
])
def test_real_files_round_trip(tmp_path: Path, name: str, variable: str, indent: int | None) -> None:
    """Rewriting a real file changes nothing: the scripts keep the exact committed format."""
    original = (ROOT / name).read_text(encoding="utf-8")
    header, body = split_js(original, variable)
    copy = tmp_path / "copy.js"
    write_js(copy, variable, json.loads(body), header=header, indent=indent)
    assert copy.read_text(encoding="utf-8") == original
