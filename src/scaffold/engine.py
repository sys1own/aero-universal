# -*- coding: utf-8 -*-
"""
``ScaffoldEngine`` -- the zero-config, out-of-tree repository generator.

End-to-end flow:

1. **Resolve** the ``source_entry`` from anywhere on the filesystem
   (:mod:`src.scaffold.source_resolver`).
2. **Shield** the source: inject the rug/pyo3 compatibility traits and align
   index types (:mod:`src.scaffold.rust_shield`).
3. **Isolate** an out-of-tree workspace -- a temp dir, or the user's
   ``distribution_directory`` (:mod:`src.scaffold.workspace`).
4. **Generate** a complete, turn-key repo: ``Cargo.toml`` / ``src/lib.rs`` /
   ``.gitignore`` / ``README.md`` / ``test_binding.py``
   (:mod:`src.scaffold.repo_generator`).
5. **Build** (optional) with a diagnostic-recovery retry loop
   (:mod:`src.scaffold.recovery`), running ``cargo`` from the generated repo so
   ``target/`` never touches the tool tree.

Every step emits a clear, ``--verbose``-friendly line through an optional
callback, and the engine never writes anything inside the tool directory.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.scaffold.recovery import DiagnosticRecoveryRunner, RecoveryResult
from src.scaffold.repo_generator import GeneratedRepo, build_spec, generate_repo
from src.scaffold.rust_shield import RustSemanticShield, ShieldReport
from src.scaffold.source_resolver import SourceEntry, copy_into_workspace, resolve_source_entry
from src.scaffold.workspace import OutOfTreeWorkspace

# A logging sink: receives one human-readable progress line at a time.
Logger = Callable[[str], None]


@dataclass
class ScaffoldResult:
    """The outcome of a scaffolding run."""

    source: Dict[str, Any]
    repo: Dict[str, Any]
    shield: Dict[str, Any]
    workspace: str
    out_of_tree: bool
    build: Optional[Dict[str, Any]] = None
    messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "repo": self.repo,
            "shield": self.shield,
            "workspace": self.workspace,
            "out_of_tree": self.out_of_tree,
            "build": self.build,
        }


class ScaffoldEngine:
    """Generate a standalone repo from a source entry, fully out-of-tree."""

    def __init__(self, logger: Optional[Logger] = None, verbose: bool = False) -> None:
        self._logger = logger
        self.verbose = verbose
        self.shield = RustSemanticShield()

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
        build: bool = False,
        keep: Optional[bool] = None,
    ) -> ScaffoldResult:
        # 1. Resolve the source from anywhere.
        entry = resolve_source_entry(source_entry, base_dir=base_dir)
        self._log(f"resolved source_entry -> {entry.path}  (language: {entry.language})")
        source_text = entry.read_text()

        # 2. Shield rug/pyo3 sources (no-op for anything else).
        shield_report = self._shield(entry, source_text)

        # 3. Out-of-tree workspace (temp dir, or the distribution directory).
        workspace = OutOfTreeWorkspace(distribution_directory=distribution_directory, keep=keep)
        workspace.create()
        self._log(
            f"workspace: {workspace.root}  "
            f"({'temporary, auto-cleaned' if workspace.is_temporary else 'distribution directory'})"
        )

        # 4. Generate the complete standalone repository.
        spec = build_spec(name or entry.stem, shield_report.source, dependencies=dependencies)
        self._log(
            f"crate '{spec.name}'  deps={list(spec.dependencies) or '(none)'}  "
            f"crate-type={spec.crate_type}  pymodule={spec.python_module or '-'}"
        )
        repo = generate_repo(spec, workspace.root)
        for written in repo.files:
            self._log(f"  + {written}")
        # Record where the original came from (the file itself stays put).
        copy_into_workspace(entry, workspace.root / "src" / "lib.rs", content=spec.source)

        # 5. Optional build with diagnostic recovery (cargo runs in the repo).
        build_info: Optional[Dict[str, Any]] = None
        if build:
            build_info = self._build_with_recovery(repo).to_dict()

        result = ScaffoldResult(
            source=entry.to_dict(),
            repo=repo.to_dict(),
            shield=shield_report.to_dict(),
            workspace=str(workspace.root),
            out_of_tree=True,
            build=build_info,
        )
        return result

    # ------------------------------------------------------------------

    def _shield(self, entry: SourceEntry, source_text: str) -> ShieldReport:
        if entry.language != "rust":
            return ShieldReport(source=source_text)
        report = self.shield.apply(source_text)
        if report.anchors:
            self._log(f"shield: detected anchors {sorted(report.anchors)}")
        for fix in report.applied:
            self._log(f"shield: applied {fix}")
        if report.anchors and not report.applied:
            self._log("shield: source already compatible; no fixes needed")
        return report

    def _build_with_recovery(self, repo: GeneratedRepo) -> RecoveryResult:
        """Build the generated crate from its own root, recovering on failure."""
        from src.build.compilers import RustCompiler

        compiler = RustCompiler()
        if compiler.discover() is None:
            self._log("build: no cargo/rustc toolchain found; skipping compile")
            return RecoveryResult(succeeded=False, final_output="no rust toolchain")

        crate_root = repo.root

        def _run_cargo() -> tuple:
            # RustCompiler runs cargo from the crate root and reports the
            # artefact dir inside repo/target -- guaranteed out-of-tree.
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
