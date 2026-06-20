# -*- coding: utf-8 -*-
"""Lean compiler invocation wrappers for the Aero build engine.

Each language backend is a subclass of :class:`CompilerBackend` — a minimal,
plugin-ready interface that knows how to:

1. **discover** the compiler binary on ``$PATH``,
2. **build a command line** from a :class:`~build_graph.TargetNode`, and
3. **execute** the compilation, returning a structured :class:`CompileResult`.

Supported backends
------------------
* :class:`CCompiler`    -- C  via ``gcc`` / ``clang``
* :class:`CppCompiler`  -- C++ via ``g++`` / ``clang++``
* :class:`RustCompiler` -- Rust via ``cargo`` (preferred) or ``rustc``
* :class:`PythonRuntime` -- validates/byte-compiles Python sources
* :class:`NodeRuntime`   -- validates Node.js sources via ``node --check``

The registry :data:`BACKENDS` maps language names (as they appear in
``blueprint.aero`` target blocks) to backend classes.  The factory
:func:`get_backend` looks up and instantiates the right one.

Design note: the interface is deliberately thin so each backend can later be
extracted into a standalone plugin package without touching the core engine.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Type

logger = logging.getLogger("aero.compilers")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CompileResult:
    """Outcome of a single target compilation."""

    target_name: str
    success: bool
    command: List[str]
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    output_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_summary(self) -> str:
        """First non-empty line of stderr, or a generic message."""
        for line in self.stderr.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return "unknown error" if not self.success else ""


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class CompilerBackend(ABC):
    """Plugin-ready interface for a language compiler / runtime."""

    language: str = ""

    @abstractmethod
    def discover(self) -> Optional[str]:
        """Return the absolute path to the compiler binary, or ``None``."""

    @abstractmethod
    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        """Construct the full command-line argument list."""

    def compile(
        self,
        target_name: str,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> CompileResult:
        """Discover the compiler, build the command, execute, return result."""
        binary = self.discover()
        if binary is None:
            return CompileResult(
                target_name=target_name,
                success=False,
                command=[],
                stderr=f"no {self.language} compiler found on PATH",
                return_code=-1,
            )
        cmd = self.build_command(sources, output, flags, defines, workdir)
        return self._run(target_name, cmd, workdir)

    def _run(
        self,
        target_name: str,
        cmd: List[str],
        workdir: Optional[Path] = None,
    ) -> CompileResult:
        cwd = str(workdir) if workdir else None
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=cwd,
            )
            return CompileResult(
                target_name=target_name,
                success=proc.returncode == 0,
                command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
            )
        except FileNotFoundError:
            return CompileResult(
                target_name=target_name,
                success=False,
                command=cmd,
                stderr=f"compiler binary not found: {cmd[0]}",
                return_code=-1,
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                target_name=target_name,
                success=False,
                command=cmd,
                stderr="compilation timed out (300s limit)",
                return_code=-1,
            )


# ---------------------------------------------------------------------------
# C / C++
# ---------------------------------------------------------------------------

_C_CANDIDATES = ("gcc", "clang", "cc")
_CPP_CANDIDATES = ("g++", "clang++", "c++")


class CCompiler(CompilerBackend):
    language = "c"

    def discover(self) -> Optional[str]:
        for name in _C_CANDIDATES:
            path = shutil.which(name)
            if path:
                return path
        return None

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "gcc"
        cmd: List[str] = [binary]
        cmd.extend(flags)
        for define in defines:
            cmd.extend(["-D", define])
        cmd.extend(sources)
        if output:
            cmd.extend(["-o", output])
        return cmd


class CppCompiler(CompilerBackend):
    language = "cpp"

    def discover(self) -> Optional[str]:
        for name in _CPP_CANDIDATES:
            path = shutil.which(name)
            if path:
                return path
        return None

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "g++"
        cmd: List[str] = [binary]
        cmd.extend(flags)
        for define in defines:
            cmd.extend(["-D", define])
        cmd.extend(sources)
        if output:
            cmd.extend(["-o", output])
        return cmd


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class RustCompiler(CompilerBackend):
    language = "rust"

    def discover(self) -> Optional[str]:
        cargo = shutil.which("cargo")
        if cargo:
            return cargo
        return shutil.which("rustc")

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "cargo"
        if os.path.basename(binary) == "cargo":
            cmd: List[str] = [binary, "build"]
            if flags:
                cmd.append("--")
                cmd.extend(flags)
            return cmd
        # rustc fallback
        cmd = [binary]
        cmd.extend(flags)
        cmd.extend(sources)
        if output:
            cmd.extend(["-o", output])
        return cmd


# ---------------------------------------------------------------------------
# Python (interpreted -- syntax-check / byte-compile)
# ---------------------------------------------------------------------------

_PYTHON_CANDIDATES = ("python3", "python")


class PythonRuntime(CompilerBackend):
    language = "python"

    def discover(self) -> Optional[str]:
        for name in _PYTHON_CANDIDATES:
            path = shutil.which(name)
            if path:
                return path
        return None

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "python3"
        cmd: List[str] = [binary, "-m", "py_compile"]
        cmd.extend(sources)
        return cmd


# ---------------------------------------------------------------------------
# Node.js (interpreted -- syntax-check)
# ---------------------------------------------------------------------------


class NodeRuntime(CompilerBackend):
    language = "node"

    def discover(self) -> Optional[str]:
        return shutil.which("node")

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "node"
        cmd: List[str] = [binary, "--check"]
        cmd.extend(sources)
        return cmd


# ---------------------------------------------------------------------------
# Fortran
# ---------------------------------------------------------------------------

_FORTRAN_CANDIDATES = ("gfortran", "ifort", "flang")


class FortranCompiler(CompilerBackend):
    language = "fortran"

    def discover(self) -> Optional[str]:
        for name in _FORTRAN_CANDIDATES:
            path = shutil.which(name)
            if path:
                return path
        return None

    def build_command(
        self,
        sources: Sequence[str],
        output: Optional[str] = None,
        flags: Sequence[str] = (),
        defines: Sequence[str] = (),
        workdir: Optional[Path] = None,
    ) -> List[str]:
        binary = self.discover() or "gfortran"
        cmd: List[str] = [binary]
        cmd.extend(flags)
        for define in defines:
            cmd.extend(["-D", define])
        cmd.extend(sources)
        if output:
            cmd.extend(["-o", output])
        return cmd


# ---------------------------------------------------------------------------
# Registry + factory
# ---------------------------------------------------------------------------

BACKENDS: Dict[str, Type[CompilerBackend]] = {
    "c": CCompiler,
    "cpp": CppCompiler,
    "rust": RustCompiler,
    "python": PythonRuntime,
    "node": NodeRuntime,
    "fortran": FortranCompiler,
}


def get_backend(language: str) -> Optional[CompilerBackend]:
    """Look up and instantiate the compiler backend for *language*."""
    cls = BACKENDS.get(language.lower())
    if cls is None:
        return None
    return cls()


def compile_target(
    target_name: str,
    language: str,
    sources: Sequence[str],
    output: Optional[str] = None,
    flags: Sequence[str] = (),
    defines: Sequence[str] = (),
    workdir: Optional[Path] = None,
) -> CompileResult:
    """One-shot: look up the backend and compile a target."""
    backend = get_backend(language)
    if backend is None:
        return CompileResult(
            target_name=target_name,
            success=False,
            command=[],
            stderr=f"unsupported language: {language}",
            return_code=-1,
        )
    return backend.compile(target_name, sources, output, flags, defines, workdir)
