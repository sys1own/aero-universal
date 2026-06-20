# -*- coding: utf-8 -*-
"""Clean, scannable terminal UI for the Aero build engine.

Inspired by Cargo and Bun: each phase of the pipeline gets a bold,
bracketed tag, coloured where the terminal supports it, so progress is
immediately visible at a glance::

    [Parsing]    blueprint.aero
    [Validating] 3 targets, 0 errors
    [Compiling]  core_engine (cpp)  ........................ ok
    [Compiling]  bindings (python)  ........................ ok
    [Success]    3 targets compiled in 1.2s

All output goes through a single :class:`AeroUI` instance so the rest
of the codebase never writes raw ``print()`` during a managed build.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import IO, List, Optional

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty()

_RESET = "" if _NO_COLOR else "\033[0m"
_BOLD = "" if _NO_COLOR else "\033[1m"
_DIM = "" if _NO_COLOR else "\033[2m"
_GREEN = "" if _NO_COLOR else "\033[32m"
_CYAN = "" if _NO_COLOR else "\033[36m"
_YELLOW = "" if _NO_COLOR else "\033[33m"
_RED = "" if _NO_COLOR else "\033[31m"
_MAGENTA = "" if _NO_COLOR else "\033[35m"
_WHITE = "" if _NO_COLOR else "\033[37m"

_TAG_COLORS = {
    "Parsing": _CYAN,
    "Validating": _MAGENTA,
    "Resolving": _MAGENTA,
    "Compiling": _GREEN,
    "Compiled": _GREEN,
    "Skipped": _YELLOW,
    "Success": _GREEN,
    "Error": _RED,
    "Warning": _YELLOW,
    "Info": _CYAN,
    "Plan": _CYAN,
    "Debug": _DIM,
    "Hint": _YELLOW,
}

_TAG_WIDTH = 13  # pad tag to consistent width


def _format_tag(tag: str) -> str:
    color = _TAG_COLORS.get(tag, _WHITE)
    padded = tag.ljust(_TAG_WIDTH)
    return f"{_BOLD}{color}[{padded}]{_RESET}"


def _format_dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def _format_bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


def _format_error_header(text: str) -> str:
    return f"{_BOLD}{_RED}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------


@dataclass
class _Timer:
    _start: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def elapsed_str(self) -> str:
        secs = self.elapsed()
        if secs < 1.0:
            return f"{secs * 1000:.0f}ms"
        return f"{secs:.1f}s"


# ---------------------------------------------------------------------------
# Main UI class
# ---------------------------------------------------------------------------


class AeroUI:
    """Stateful, phase-aware terminal writer."""

    def __init__(self, stream: Optional[IO[str]] = None) -> None:
        self._stream: IO[str] = stream or sys.stdout
        self._timer = _Timer()
        self._compiled: int = 0
        self._skipped: int = 0
        self._failed: int = 0
        self._errors: List[str] = []

    # -- low-level ---------------------------------------------------------

    def _write(self, text: str) -> None:
        self._stream.write(text + "\n")
        self._stream.flush()

    # -- phase tags --------------------------------------------------------

    def tag(self, phase: str, message: str) -> None:
        self._write(f"{_format_tag(phase)} {message}")

    def parsing(self, path: str) -> None:
        self.tag("Parsing", path)

    def validating(self, target_count: int, error_count: int = 0) -> None:
        errors = f", {_format_error_header(f'{error_count} error(s)')}" if error_count else ", 0 errors"
        self.tag("Validating", f"{target_count} target{'s' if target_count != 1 else ''}{errors}")

    def resolving(self, target_count: int, stage_count: int) -> None:
        self.tag(
            "Resolving",
            f"build order: {target_count} target{'s' if target_count != 1 else ''}, "
            f"{stage_count} stage{'s' if stage_count != 1 else ''}",
        )

    def compiling(self, target_name: str, language: str) -> None:
        self.tag("Compiling", f"{target_name} ({language})")

    def compiled(self, target_name: str, language: str, elapsed: Optional[str] = None) -> None:
        self._compiled += 1
        suffix = f" {_format_dim(elapsed)}" if elapsed else ""
        self.tag("Compiled", f"{target_name} ({language}){suffix}")

    def skipped(self, target_name: str, reason: str = "") -> None:
        self._skipped += 1
        msg = f"{target_name}"
        if reason:
            msg += f" {_format_dim(reason)}"
        self.tag("Skipped", msg)

    def compile_error(self, target_name: str, summary: str) -> None:
        self._failed += 1
        self._errors.append(f"{target_name}: {summary}")
        self.tag("Error", f"{target_name}: {summary}")

    def success(self) -> None:
        total = self._compiled + self._skipped
        parts = [f"{self._compiled} compiled"]
        if self._skipped:
            parts.append(f"{self._skipped} skipped")
        elapsed = self._timer.elapsed_str()
        self.tag("Success", f"{', '.join(parts)} in {elapsed}")

    def failure(self) -> None:
        elapsed = self._timer.elapsed_str()
        self.tag("Error", f"build failed: {self._failed} error(s) in {elapsed}")

    def info(self, message: str) -> None:
        self.tag("Info", message)

    def debug(self, message: str) -> None:
        self.tag("Debug", message)

    def debug_block(self, title: str, lines: List[str]) -> None:
        """Print a titled, indented block of debug detail (e.g. a manifest)."""
        self.tag("Debug", _format_bold(title))
        for line in lines:
            self._write(f"  {_format_dim(line)}")

    def warning(self, message: str) -> None:
        self.tag("Warning", message)

    def plan(self, message: str) -> None:
        self.tag("Plan", message)

    # -- error report ------------------------------------------------------

    def build_failure_report(
        self, target_name: str, stderr: str, suggestions: Optional[List[str]] = None
    ) -> None:
        """Print a formatted compiler-error report under a clear header.

        ``suggestions`` (e.g. from the Rust error analyser) are rendered in a
        highlighted "Possible cause" block beneath the raw compiler output.
        """
        self._write("")
        self._write(f"{_format_error_header('Aero Build Failure')}")
        self._write(f"{_format_error_header('─' * 40)}")
        self._write(f"  target: {_format_bold(target_name)}")
        self._write("")
        for line in stderr.splitlines():
            self._write(f"  {line}")
        if suggestions:
            self._write("")
            self._write(f"  {_BOLD}{_YELLOW}Possible cause (Aero analysis):{_RESET}")
            for line in suggestions:
                self._write(f"    {_YELLOW}→{_RESET} {line}")
        self._write("")
        self._write(f"{_format_error_header('─' * 40)}")

    # -- summary -----------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        return self._failed > 0

    @property
    def stats(self) -> dict:
        return {
            "compiled": self._compiled,
            "skipped": self._skipped,
            "failed": self._failed,
            "elapsed": self._timer.elapsed_str(),
        }
