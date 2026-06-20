"""
Automated Physical Validation.

Runs a validation suite (e.g. N-body, Schwarzschild-metric benchmarks) against
the built binary, compares the output to known-good results within a tolerance,
and produces a pass/fail report with per-case detail.  When configured as a
gatekeeper (``validation_required = true``) the evolutionary engine excludes
candidates that fail validation from the Pareto front.

Accepted output formats from the validation command:

* JSON: ``{"passed": true, "cases": [{"name": "...", "passed": true,
  "error": 1e-9}]}``
* lines: ``case_name: PASS`` / ``case_name: FAIL`` / ``case_name error=1e-9``

If the command emits nothing structured, the overall exit code decides pass/fail.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

Runner = Callable[[List[str], Optional[str]], Tuple[int, str, str]]


@dataclass
class ValidationCaseResult:
    name: str
    passed: bool
    error: Optional[float] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "error": self.error, "message": self.message}


@dataclass
class ValidationReport:
    passed: bool
    cases: List[ValidationCaseResult] = field(default_factory=list)
    returncode: int = 0
    summary: str = ""
    error: str = ""

    @property
    def num_passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def num_failed(self) -> int:
        return sum(1 for c in self.cases if not c.passed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "returncode": self.returncode,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "cases": [c.to_dict() for c in self.cases],
            "summary": self.summary,
            "error": self.error,
        }


class Validator:
    """Runs the validation suite and reports pass/fail."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, runner: Optional[Runner] = None) -> None:
        self.config = config or {}
        v = self.config.get("validation", {}) or {}
        self.suite = v.get("suite", "") or ""
        self.tolerance = float(v.get("tolerance", 1e-8))
        self.test_cases = list(v.get("test_cases", []))
        self.execution_command = v.get("execution_command", "") or ""
        self.validation_required = bool(v.get("validation_required", True))
        self._runner = runner or self._default_runner

    @property
    def enabled(self) -> bool:
        return bool(self.execution_command)

    @property
    def is_gatekeeper(self) -> bool:
        return self.validation_required

    # ------------------------------------------------------------------

    def run(self, workdir: Optional[str] = None) -> ValidationReport:
        if not self.enabled:
            # No suite configured -> treat as a vacuous pass so it never blocks.
            return ValidationReport(passed=True, summary="validation disabled")

        try:
            command = shlex.split(self.execution_command)
        except ValueError as exc:
            return ValidationReport(passed=False, error=f"bad execution_command: {exc}")

        rc, stdout, stderr = self._runner(command, workdir)
        report = self._parse(stdout, rc)
        report.returncode = rc
        if rc != 0 and not report.cases:
            report.passed = False
            report.error = stderr.strip()[:500]
        report.summary = (
            f"{report.num_passed} passed, {report.num_failed} failed "
            f"(rc={rc}, tolerance={self.tolerance})"
        )
        return report

    # ------------------------------------------------------------------

    def _parse(self, stdout: str, rc: int) -> ValidationReport:
        # 1) JSON form.
        blob = self._extract_json(stdout)
        if isinstance(blob, dict) and "cases" in blob:
            cases: List[ValidationCaseResult] = []
            for entry in blob.get("cases", []):
                name = str(entry.get("name", "case"))
                err = entry.get("error")
                if "passed" in entry:
                    passed = bool(entry["passed"])
                elif err is not None:
                    passed = abs(float(err)) <= self.tolerance
                else:
                    passed = False
                cases.append(
                    ValidationCaseResult(
                        name=name,
                        passed=passed,
                        error=float(err) if err is not None else None,
                    )
                )
            overall = bool(blob.get("passed", all(c.passed for c in cases)))
            return ValidationReport(passed=overall and bool(cases), cases=cases)

        # 2) Line form.
        cases = self._parse_lines(stdout)
        if cases:
            return ValidationReport(passed=all(c.passed for c in cases), cases=cases)

        # 3) Nothing structured -> defer to exit code.
        return ValidationReport(passed=(rc == 0), cases=[])

    def _parse_lines(self, stdout: str) -> List[ValidationCaseResult]:
        cases: List[ValidationCaseResult] = []
        pass_fail_re = re.compile(r"^\s*([\w./\-]+)\s*[:=]\s*(PASS|FAIL|OK|ERROR)\b", re.IGNORECASE)
        error_re = re.compile(r"^\s*([\w./\-]+)\s+.*?error\s*[=:]\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", re.IGNORECASE)
        for line in stdout.splitlines():
            m = pass_fail_re.match(line)
            if m:
                verdict = m.group(2).upper()
                cases.append(
                    ValidationCaseResult(name=m.group(1), passed=verdict in ("PASS", "OK"))
                )
                continue
            m = error_re.match(line)
            if m:
                err = float(m.group(2))
                cases.append(
                    ValidationCaseResult(
                        name=m.group(1), passed=abs(err) <= self.tolerance, error=err
                    )
                )
        return cases

    @staticmethod
    def _extract_json(text: str) -> Optional[Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            pass
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    def _default_runner(cmd: List[str], workdir: Optional[str]) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, "", str(exc)
        return (
            proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"),
        )
