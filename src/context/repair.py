"""
Automatic code repair for ingested sources.

Applies a configurable set of repair rules to Python source text:

* ``auto_import``    -- add ``import`` statements for well-known undefined names.
* ``remove_unused``  -- delete import statements whose bound names are never used.
* ``type_inference`` -- add ``-> None`` to single-line functions that never
                        return a value.

Every rule is applied defensively: after each edit the result is re-parsed, and
any change that would break the syntax is rolled back.  Edits are line-based so
comments and formatting are preserved (no full AST round-trip).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.context.analyser import CodeAnalyser, FileFindings

# Well-known name -> import statement used by the ``auto_import`` rule.
_KNOWN_IMPORTS: Dict[str, str] = {
    "math": "import math",
    "os": "import os",
    "sys": "import sys",
    "json": "import json",
    "re": "import re",
    "time": "import time",
    "random": "import random",
    "itertools": "import itertools",
    "functools": "import functools",
    "np": "import numpy as np",
    "pd": "import pandas as pd",
    "plt": "import matplotlib.pyplot as plt",
    "Path": "from pathlib import Path",
    "dataclass": "from dataclasses import dataclass",
    "field": "from dataclasses import field",
    "Dict": "from typing import Dict",
    "List": "from typing import List",
    "Optional": "from typing import Optional",
    "Any": "from typing import Any",
    "Tuple": "from typing import Tuple",
    "Set": "from typing import Set",
    "Callable": "from typing import Callable",
}


@dataclass
class RepairResult:
    source: str
    changes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {"changes": self.changes}


class CodeRepairer:
    """Applies repair rules to Python source, preserving formatting."""

    def __init__(self) -> None:
        self.analyser = CodeAnalyser()

    def repair(self, source: str, rules: List[str], path: str = "<source>") -> RepairResult:
        result = RepairResult(source=source)
        if not self._parses(result.source):
            return result  # never touch un-parseable input

        if "remove_unused" in rules:
            result = self._apply_safely(result, self._remove_unused, path)
        if "auto_import" in rules:
            result = self._apply_safely(result, self._auto_import, path)
        if "type_inference" in rules:
            result = self._apply_safely(result, self._type_inference, path)
        return result

    # ------------------------------------------------------------------
    # Rule implementations -- each returns (new_source, changes)
    # ------------------------------------------------------------------

    def _auto_import(self, source: str, path: str) -> Tuple[str, List[str]]:
        findings = self.analyser.analyse(source, path, "python")
        to_add = [
            _KNOWN_IMPORTS[name]
            for name in findings.undefined_names
            if name in _KNOWN_IMPORTS
        ]
        if not to_add:
            return source, []
        # De-duplicate while preserving order, and skip any already present.
        existing = set(source.splitlines())
        statements = [s for i, s in enumerate(dict.fromkeys(to_add)) if s not in existing]
        if not statements:
            return source, []
        lines = source.splitlines()
        insert_at = self._import_insertion_point(lines)
        new_lines = lines[:insert_at] + statements + lines[insert_at:]
        changes = [f"auto_import: added '{s}'" for s in statements]
        return "\n".join(new_lines) + ("\n" if source.endswith("\n") else ""), changes

    def _remove_unused(self, source: str, path: str) -> Tuple[str, List[str]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, []
        findings = self.analyser.analyse(source, path, "python")
        unused = set(findings.unused_imports)
        if not unused:
            return source, []

        remove_lines: set = set()
        changes: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                continue
            bound = [
                (alias.asname or (alias.name if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]))
                for alias in node.names
            ]
            # Only remove when *every* name bound by this statement is unused.
            if bound and all(name in unused for name in bound):
                start = node.lineno
                end = getattr(node, "end_lineno", node.lineno)
                remove_lines.update(range(start, end + 1))
                changes.append(f"remove_unused: dropped import of {', '.join(bound)}")

        if not remove_lines:
            return source, []
        lines = source.splitlines()
        kept = [ln for i, ln in enumerate(lines, start=1) if i not in remove_lines]
        return "\n".join(kept) + ("\n" if source.endswith("\n") else ""), changes

    def _type_inference(self, source: str, path: str) -> Tuple[str, List[str]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, []

        # Functions with no annotation that never return a value -> ``-> None``.
        targets: Dict[int, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is None:
                returns_value = any(
                    isinstance(n, ast.Return) and n.value is not None
                    for n in ast.walk(node)
                )
                if not returns_value:
                    targets[node.lineno] = node.name
        if not targets:
            return source, []

        lines = source.splitlines()
        changes: List[str] = []
        for lineno, name in targets.items():
            idx = lineno - 1
            if idx >= len(lines):
                continue
            line = lines[idx]
            # Only handle single-line signatures ending in ``):``.
            m = re.match(r"^(\s*(?:async\s+)?def\s+\w+\s*\(.*\))\s*:\s*$", line)
            if m:
                lines[idx] = f"{m.group(1)} -> None:"
                changes.append(f"type_inference: annotated '{name}' return as None")
        if not changes:
            return source, []
        return "\n".join(lines) + ("\n" if source.endswith("\n") else ""), changes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_safely(self, result: RepairResult, rule, path: str) -> RepairResult:
        new_source, changes = rule(result.source, path)
        if changes and self._parses(new_source):
            return RepairResult(source=new_source, changes=result.changes + changes)
        return result  # roll back if the edit broke parsing or did nothing

    @staticmethod
    def _parses(source: str) -> bool:
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def _import_insertion_point(lines: List[str]) -> int:
        """Pick a line index after the module docstring / ``__future__`` imports."""
        idx = 0
        n = len(lines)
        # Skip a shebang.
        if idx < n and lines[idx].startswith("#!"):
            idx += 1
        # Skip a module docstring.
        while idx < n and not lines[idx].strip():
            idx += 1
        if idx < n and re.match(r'\s*[ruRU]?(\'\'\'|""")', lines[idx]):
            quote = '"""' if '"""' in lines[idx] else "'''"
            if lines[idx].count(quote) >= 2 and len(lines[idx].strip()) > 3:
                idx += 1  # single-line docstring
            else:
                idx += 1
                while idx < n and quote not in lines[idx]:
                    idx += 1
                idx += 1
        # Keep __future__ imports first.
        while idx < n and lines[idx].startswith("from __future__"):
            idx += 1
        return idx
