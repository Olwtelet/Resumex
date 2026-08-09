"""User-facing terminal output.

Deliberately tiny and dependency-free. Colour is disabled automatically when
output is redirected, when ``NO_COLOR`` is set, or on a dumb terminal.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
}

OK = "[ok]"
WARN = "[!!]"
FAIL = "[xx]"
SKIP = "[--]"


def color_enabled(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def style(text: str, *names: str, stream: TextIO | None = None) -> str:
    if not names or not color_enabled(stream):
        return text
    prefix = "".join(_CODES[name] for name in names if name in _CODES)
    return f"{prefix}{text}{_CODES['reset']}" if prefix else text


def write(message: str = "", *, stream: TextIO | None = None) -> None:
    print(message, file=stream or sys.stdout)


def heading(text: str) -> None:
    write()
    write(style(text, "bold"))


def step(text: str) -> None:
    write(f"  {style('->', 'cyan')} {text}")


def detail(text: str) -> None:
    write(style(f"     {text}", "dim"))


def success(text: str) -> None:
    write(f"{style(OK, 'green')} {text}")


def warn(text: str) -> None:
    write(f"{style(WARN, 'yellow')} {text}", stream=sys.stderr)


def error(text: str) -> None:
    write(f"{style(FAIL, 'red')} {text}", stream=sys.stderr)


def status(state: str, label: str, note: str = "") -> None:
    """One line of `resumex doctor` output."""
    marks = {
        "ok": (OK, "green"),
        "warn": (WARN, "yellow"),
        "fail": (FAIL, "red"),
        "skip": (SKIP, "dim"),
    }
    mark, colour = marks[state]
    line = f"{style(mark, colour)} {label}"
    if note:
        line += f"  {style(note, 'dim')}"
    write(line)


def table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> None:
    """Print a left-aligned plain-text table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    write(style(line(headers), "bold"))
    write(style("  ".join("-" * w for w in widths), "dim"))
    for row in rows:
        write(line(row))
