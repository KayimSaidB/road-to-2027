"""Read and write the data files the site loads: `<header>window.<VARIABLE> = <JSON>;`.

The site has no build step: index.html loads data/*.js with plain <script> tags, and each file
assigns one global (window.POLLS, window.SOCIAL...). The header is an optional comment.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MissingVariableError(ValueError):
    """The file does not assign the expected `window.<VARIABLE>`."""


def split_js(text: str, variable: str) -> tuple[str, str]:
    """'/* header */\\nwindow.X = {...};\\n' -> ('/* header */\\n', '{...}')"""
    prefix = f"window.{variable} = "
    if prefix not in text:
        raise MissingVariableError(f"'{prefix.strip()}' not found")
    header, rest = text.split(prefix, 1)
    return header, rest.rsplit(";", 1)[0]


def read_js(path: Path | str, variable: str) -> Any:
    """The JSON value assigned to window.<variable> in `path`."""
    _, body = split_js(Path(path).read_text(encoding="utf-8"), variable)
    return json.loads(body)


def write_js(path: Path | str, variable: str, data: Any, *, header: str = "", indent: int | None = None) -> None:
    """Write `data` as window.<variable>. indent=None: compact, on one line (generated files)."""
    if indent is None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        body = json.dumps(data, ensure_ascii=False, indent=indent)
    Path(path).write_text(f"{header}window.{variable} = {body};\n", encoding="utf-8")
