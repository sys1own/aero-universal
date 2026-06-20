"""
Physics-Framework Integration.

Detects whether the target code uses known physics frameworks (deal.II,
OpenFOAM, or a custom library), derives the compiler/linker flags they require,
and can emit ready-to-use CMake / Makefile snippets.  Framework versions can be
exposed to the evolutionary engine as genes so it can search versions for the
best performance.

All detection is best-effort and non-fatal: an unconfigured or unused framework
simply contributes no flags.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FrameworkFlags:
    name: str
    used: bool = False
    version: str = ""
    include_dirs: List[str] = field(default_factory=list)
    libs: List[str] = field(default_factory=list)
    compiler_flags: List[str] = field(default_factory=list)
    linker_flags: List[str] = field(default_factory=list)
    detected_via: str = "config"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "used": self.used,
            "version": self.version,
            "include_dirs": self.include_dirs,
            "libs": self.libs,
            "compiler_flags": self.compiler_flags,
            "linker_flags": self.linker_flags,
            "detected_via": self.detected_via,
        }


# Header signatures that indicate a framework is in use.
_USAGE_SIGNATURES = {
    "dealii": [r"#\s*include\s*[<\"]deal\.II/"],
    "openfoam": [r"#\s*include\s*[<\"]fvCFD\.H", r"#\s*include\s*[<\"]OpenFOAM"],
}
_SOURCE_GLOBS = ("*.c", "*.cc", "*.cpp", "*.cxx", "*.C", "*.h", "*.hpp", "*.hh")


class FrameworkIntegration:
    """Detects framework usage and emits build configuration for it."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.frameworks: Dict[str, Dict[str, Any]] = dict(self.config.get("frameworks", {}) or {})

    def configured(self) -> List[str]:
        return list(self.frameworks.keys())

    # ------------------------------------------------------------------
    # Usage detection
    # ------------------------------------------------------------------

    def detect_usage(self, project_root: Path, mapper: Any = None) -> Dict[str, bool]:
        """Return {framework -> used} by scanning source headers."""
        project_root = Path(project_root)
        used = {name: False for name in self.frameworks}

        # Gather source text once.
        texts: List[str] = []
        for pattern in _SOURCE_GLOBS:
            for path in project_root.rglob(pattern):
                try:
                    texts.append(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    continue
        blob = "\n".join(texts)

        for name in self.frameworks:
            signatures = _USAGE_SIGNATURES.get(name)
            if signatures:
                used[name] = any(re.search(sig, blob) for sig in signatures)
            else:
                # Custom frameworks: "used" if any configured include dir appears,
                # otherwise assume configured == intended to be linked.
                spec = self.frameworks[name]
                inc = spec.get("include_dirs", [])
                if inc and blob:
                    used[name] = any(str(d).strip("/") in blob for d in inc)
                else:
                    used[name] = True
        return used

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def flags_for(self, name: str) -> FrameworkFlags:
        spec = self.frameworks.get(name, {})
        if name == "dealii":
            return self._dealii_flags(spec)
        if name == "openfoam":
            return self._openfoam_flags(spec)
        return self._custom_flags(name, spec)

    def all_flags(self, project_root: Optional[Path] = None) -> Dict[str, FrameworkFlags]:
        used_map = self.detect_usage(project_root) if project_root else {n: True for n in self.frameworks}
        result: Dict[str, FrameworkFlags] = {}
        for name in self.frameworks:
            flags = self.flags_for(name)
            flags.used = used_map.get(name, True)
            result[name] = flags
        return result

    def aggregate_flags(self, project_root: Optional[Path] = None) -> Dict[str, List[str]]:
        """Combined compiler + linker flags across *used* frameworks."""
        compiler: List[str] = []
        linker: List[str] = []
        for flags in self.all_flags(project_root).values():
            if not flags.used:
                continue
            for flag in flags.compiler_flags:
                if flag not in compiler:
                    compiler.append(flag)
            for flag in flags.linker_flags:
                if flag not in linker:
                    linker.append(flag)
        return {"compiler_flags": compiler, "linker_flags": linker}

    def _dealii_flags(self, spec: Dict[str, Any]) -> FrameworkFlags:
        version = str(spec.get("version", ""))
        deal_dir = os.environ.get("DEAL_II_DIR")
        flags = FrameworkFlags(name="dealii", version=version)
        if deal_dir:
            flags.include_dirs = [os.path.join(deal_dir, "include")]
            flags.compiler_flags = [f"-I{os.path.join(deal_dir, 'include')}"]
            flags.linker_flags = [f"-L{os.path.join(deal_dir, 'lib')}", "-ldeal_II"]
            flags.detected_via = "env:DEAL_II_DIR"
        else:
            flags.linker_flags = ["-ldeal_II"]
            flags.detected_via = "config"
        flags.libs = ["deal_II"]
        return flags

    def _openfoam_flags(self, spec: Dict[str, Any]) -> FrameworkFlags:
        version = str(spec.get("version", ""))
        foam_src = os.environ.get("FOAM_SRC") or os.environ.get("WM_PROJECT_DIR")
        flags = FrameworkFlags(name="openfoam", version=version)
        if foam_src:
            flags.include_dirs = [
                os.path.join(foam_src, "finiteVolume", "lnInclude"),
                os.path.join(foam_src, "OpenFOAM", "lnInclude"),
            ]
            flags.compiler_flags = [f"-I{d}" for d in flags.include_dirs]
            flags.detected_via = "env:FOAM_SRC"
        else:
            flags.detected_via = "config"
        flags.libs = ["OpenFOAM", "finiteVolume"]
        flags.linker_flags = ["-lOpenFOAM", "-lfiniteVolume"]
        return flags

    def _custom_flags(self, name: str, spec: Dict[str, Any]) -> FrameworkFlags:
        flags = FrameworkFlags(name=name, version=str(spec.get("version", "")))
        base = spec.get("path", "")
        include_dirs = spec.get("include_dirs", [])
        for inc in include_dirs:
            full = os.path.join(base, inc) if base else inc
            flags.include_dirs.append(full)
            flags.compiler_flags.append(f"-I{full}")
        for lib in spec.get("libs", []):
            flags.libs.append(lib)
            # Accept either bare names ("custom" -> -lcustom) or archive paths.
            if lib.endswith((".a", ".so")) or "/" in lib:
                full = os.path.join(base, lib) if base and not os.path.isabs(lib) else lib
                flags.linker_flags.append(full)
            else:
                flags.linker_flags.append(f"-l{lib}")
        if base:
            flags.linker_flags.insert(0, f"-L{base}")
        return flags

    # ------------------------------------------------------------------
    # Build-system snippet generation
    # ------------------------------------------------------------------

    def generate_cmake(self, project_name: str = "aero_sim", project_root: Optional[Path] = None) -> str:
        lines = [
            f"# Auto-generated by Aero Multi-Tool for project '{project_name}'",
            "cmake_minimum_required(VERSION 3.13)",
            f"project({project_name} CXX)",
            "",
        ]
        used = self.detect_usage(project_root) if project_root else {n: True for n in self.frameworks}
        link_targets: List[str] = []

        for name, spec in self.frameworks.items():
            if not used.get(name, True):
                continue
            version = spec.get("version", "")
            if name == "dealii":
                ver = f" {version}" if version else ""
                lines += [
                    f"find_package(deal.II{ver} REQUIRED HINTS ${{DEAL_II_DIR}})",
                    "deal_ii_initialize_cached_variables()",
                    "",
                ]
                link_targets.append("${DEAL_II_LIBRARIES}")
            elif name == "openfoam":
                lines += [
                    "# OpenFOAM is sourced via its etc/bashrc; honour $FOAM_* env vars.",
                    "if(DEFINED ENV{FOAM_SRC})",
                    "  include_directories($ENV{FOAM_SRC}/finiteVolume/lnInclude)",
                    "endif()",
                    "",
                ]
                link_targets += ["OpenFOAM", "finiteVolume"]
            else:
                flags = self._custom_flags(name, spec)
                for inc in flags.include_dirs:
                    lines.append(f"include_directories({inc})")
                link_targets += flags.libs

        lines.append(f"add_executable({project_name} ${{SOURCES}})")
        if link_targets:
            lines.append(
                f"target_link_libraries({project_name} {' '.join(link_targets)})"
            )
        return "\n".join(lines) + "\n"

    def generate_makefile(self, project_root: Optional[Path] = None) -> str:
        agg = self.aggregate_flags(project_root)
        cxxflags = " ".join(agg["compiler_flags"])
        ldflags = " ".join(agg["linker_flags"])
        return (
            "# Auto-generated by Aero Multi-Tool\n"
            f"AERO_FRAMEWORK_CXXFLAGS = {cxxflags}\n"
            f"AERO_FRAMEWORK_LDFLAGS = {ldflags}\n"
        )

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def genome_space(self) -> Dict[str, List[str]]:
        """Framework versions become categorical genes (when several are listed)."""
        space: Dict[str, List[str]] = {}
        for name, spec in self.frameworks.items():
            versions = spec.get("versions")
            if isinstance(versions, list) and len(versions) > 1:
                space[f"{name}_version"] = [str(v) for v in versions]
        return space
