# -*- coding: utf-8 -*-
"""
``ScaffoldEngine`` -- the zero-config, out-of-tree repository generator.

End-to-end flow is routed by :mod:`src.scaffold.language_router`:

* **rust**  → Cargo layout + optional cargo build + Rust diagnostic recovery
* **python** → native Python layout + compileall/py_compile validation (no Cargo)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.scaffold.language_router import is_python, resolve_target_language
from src.scaffold.python_repo_generator import (
    PythonGeneratedRepo,
    build_python_spec,
    generate_python_repo,
)
from src.scaffold.python_validator import PythonValidationRunner
from src.scaffold.recovery import DiagnosticRecoveryRunner, RecoveryResult
from src.scaffold.repo_generator import GeneratedRepo, build_spec, generate_repo
from src.scaffold.rust_shield import RustSemanticShield, ShieldReport
from src.scaffold.source_resolver import SourceEntry, copy_into_workspace, resolve_source_entry
from src.scaffold.workspace import OutOfTreeWorkspace

Logger = Callable[[str], None]


@dataclass
class ScaffoldResult:
    """The outcome of a scaffolding run."""

    source: Dict[str, Any]
    repo: Dict[str, Any]
    shield: Dict[str, Any]
    workspace: str
    out_of_tree: bool
    language: str = "rust"
    build: Optional[Dict[str, Any]] = None
    messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "repo": self.repo,
            "shield": self.shield,
            "workspace": self.workspace,
            "out_of_tree": self.out_of_tree,
            "language": self.language,
            "build": self.build,
        }


class ScaffoldEngine:
    """Generate a standalone repo from a source entry, fully out-of-tree."""

    def __init__(self, logger: Optional[Logger] = None, verbose: bool = False) -> None:
        self._logger = logger
        self.verbose = verbose
        self.shield = RustSemanticShield()
        self._python_validator = PythonValidationRunner()

    def _log(self, message: str) -> None:
        if self.verbose and self._logger is not None:
            self._logger(message)

    # ------------------------------------------------------------------

    def scaffold(
        self,
        source_entry: str,
        name: Optional[str] = None,
        base_dir: Optional[Path] = None,
        distribution_directory: Optional[Path] = None,
        dependencies: Optional[Dict[str, Any]] = None,
        compatibility_shims: Optional[List[str]] = None,
        build: bool = False,
        keep: Optional[bool] = None,
        *,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> ScaffoldResult:
        context = context or {}
        entry = resolve_source_entry(source_entry, base_dir=base_dir)
        target_language = language or resolve_target_language(context, source_entry=entry)
        self._log(
            f"language router -> {target_language!r}  "
            f"(source={entry.path.name}, resolved={entry.language})"
        )
        self._log(f"resolved source_entry -> {entry.path}  (language: {entry.language})")

        if is_python(target_language):
            return self._scaffold_python(
                entry=entry,
                name=name,
                distribution_directory=distribution_directory,
                dependencies=dependencies,
                build=build,
                keep=keep,
            )
        return self._scaffold_rust(
            entry=entry,
            name=name,
            distribution_directory=distribution_directory,
            dependencies=dependencies,
            compatibility_shims=compatibility_shims,
            build=build,
            keep=keep,
        )

    # ------------------------------------------------------------------
    # Rust path
    # ------------------------------------------------------------------

    def _scaffold_rust(
        self,
        *,
        entry: SourceEntry,
        name: Optional[str],
        distribution_directory: Optional[Path],
        dependencies: Optional[Dict[str, Any]],
        compatibility_shims: Optional[List[str]],
        build: bool,
        keep: Optional[bool],
    ) -> ScaffoldResult:
        source_text = entry.read_text()
        shield_report = self._shield_rust(entry, source_text, compatibility_shims=compatibility_shims)

        workspace = OutOfTreeWorkspace(distribution_directory=distribution_directory, keep=keep)
        workspace.create()
        self._log(
            f"workspace: {workspace.root}  "
            f"({'temporary, auto-cleaned' if workspace.is_temporary else 'distribution directory'})"
        )

        spec = build_spec(name or entry.stem, shield_report.source, dependencies=dependencies)
        self._log(
            f"crate '{spec.name}'  deps={list(spec.dependencies) or '(none)'}  "
            f"crate-type={spec.crate_type}  pymodule={spec.python_module or '-'}"
        )
        repo = generate_repo(spec, workspace.root)
        for written in repo.files:
            self._log(f"  + {written}")
        copy_into_workspace(entry, workspace.root / "src" / "lib.rs", content=spec.source)

        build_info: Optional[Dict[str, Any]] = None
        if build:
            build_info = self._build_rust_with_recovery(repo).to_dict()
            build_info["language"] = "rust"

        return ScaffoldResult(
            source=entry.to_dict(),
            repo=repo.to_dict(),
            shield=shield_report.to_dict(),
            workspace=str(workspace.root),
            out_of_tree=True,
            language="rust",
            build=build_info,
        )

    def _shield_rust(
        self,
        entry: SourceEntry,
        source_text: str,
        compatibility_shims: Optional[List[str]] = None,
    ) -> ShieldReport:
        if entry.language != "rust":
            return ShieldReport(source=source_text)
        report = self.shield.apply(source_text, compatibility_shims=compatibility_shims)
        if report.anchors:
            self._log(f"shield: detected anchors {sorted(report.anchors)}")
        for fix in report.applied:
            self._log(f"shield: applied {fix}")
        if report.anchors and not report.applied:
            self._log("shield: source already compatible; no fixes needed")
        return report

    def _build_rust_with_recovery(self, repo: GeneratedRepo) -> RecoveryResult:
        """Build the generated crate from its own root, recovering on failure."""
        from src.build.compilers import RustCompiler

        compiler = RustCompiler()
        if compiler.discover() is None:
            self._log("build: no cargo/rustc toolchain found; skipping compile")
            return RecoveryResult(succeeded=False, final_output="no rust toolchain")

        crate_root = repo.root

        def _run_cargo() -> tuple:
            result = compiler.compile(
                target_name=repo.spec.name if repo.spec else "crate",
                sources=["src/lib.rs"],
                workdir=crate_root,
                options={"root": "."},
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            return result.success, output, result.return_code

        self._log(f"build: cargo build (cwd={crate_root}); target/ stays out-of-tree")
        runner = DiagnosticRecoveryRunner(self.shield, max_retries=1)
        recovery = runner.run(crate_root, _run_cargo)
        for attempt in recovery.attempts:
            status = "ok" if attempt.succeeded else f"failed (code {attempt.return_code})"
            extra = f"; corrections: {', '.join(attempt.corrections)}" if attempt.corrections else ""
            self._log(f"build: attempt {attempt.attempt} {status}{extra}")
        if recovery.recovered:
            self._log("build: recovered after auto-correction")
        return recovery

    # ------------------------------------------------------------------
    # Python path
    # ------------------------------------------------------------------

    def _scaffold_python(
        self,
        *,
        entry: SourceEntry,
        name: Optional[str],
        distribution_directory: Optional[Path],
        dependencies: Optional[Dict[str, Any]],
        build: bool,
        keep: Optional[bool],
    ) -> ScaffoldResult:
        source_text = entry.read_text()
        self._log("shield: skipped (Rust-specific shields not applied to Python targets)")

        workspace = OutOfTreeWorkspace(distribution_directory=distribution_directory, keep=keep)
        workspace.create()
        self._log(
            f"workspace: {workspace.root}  "
            f"({'temporary, auto-cleaned' if workspace.is_temporary else 'distribution directory'})"
        )

        dep_list: Optional[List[str]] = None
        if dependencies:
            dep_list = [str(v) if not isinstance(v, str) else v for v in dependencies.values()]

        spec = build_python_spec(
            name or entry.stem,
            source_text,
            entry_filename=entry.name,
            dependencies=dep_list,
        )
        self._log(
            f"project '{spec.name}'  entry={spec.entry_filename}  "
            f"deps={spec.dependencies or '(none)'}"
        )
        repo = generate_python_repo(spec, workspace.root)
        for written in repo.files:
            self._log(f"  + {written}")

        build_info: Optional[Dict[str, Any]] = None
        if build:
            build_info = self._validate_python(repo).to_dict()

        return ScaffoldResult(
            source=entry.to_dict(),
            repo=repo.to_dict(),
            shield={"anchors": [], "applied": [], "changed": False, "skipped": "python-target"},
            workspace=str(workspace.root),
            out_of_tree=True,
            language="python",
            build=build_info,
        )

    def _validate_python(self, repo: PythonGeneratedRepo) -> Any:
        self._log(f"validate: python bytecode check (cwd={repo.root}); cargo skipped")
        result = self._python_validator.validate_workspace(repo.root)
        attempt = result.attempts[0] if result.attempts else None
        if attempt and attempt.succeeded:
            self._log("validate: compileall/py_compile ok")
        elif attempt:
            for err in attempt.errors:
                self._log(f"validate: {err}")
        return result
