# -*- coding: utf-8 -*-
"""
Blueprint-driven scaffold build pipeline.

When a blueprint declares a ``[scaffold]`` section (with ``auto_layout`` and/or
``source_entry``), ``python main.py build --blueprint blueprint.aero`` routes
through this five-step workflow instead of the legacy in-tree orchestrator:

1. Read and validate absolute ``source_entry`` paths from anywhere on disk.
2. Run ingestion sanity filters / compatibility shims in-memory.
3. Provision an out-of-tree workspace at ``distribution_directory``.
4. Synthesize a turn-key repository layout (Cargo.toml, src/lib.rs, …).
5. Execute ``cargo build --release`` entirely inside that external workspace.

The ``aero-universal`` tool directory is never written to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.scaffold.engine import ScaffoldEngine, ScaffoldResult
from src.scaffold.source_resolver import SourceEntryNotFound
from src.scaffold.workspace import WorkspaceLocationError

Logger = Callable[[str], None]
STEP_COUNT = 5


@dataclass
class PipelineResult:
    """Outcome of a blueprint scaffold build."""

    succeeded: bool
    scaffold: ScaffoldResult
    steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "workspace": self.scaffold.workspace,
            "steps": list(self.steps),
            "build": self.scaffold.build,
        }


def scaffold_config_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return the normalized ``scaffold`` section from a build context."""
    return dict(context.get("scaffold") or {})


def should_run_scaffold_pipeline(context: Dict[str, Any]) -> bool:
    """True when the blueprint requests out-of-tree scaffold layout/build."""
    cfg = scaffold_config_from_context(context)
    return bool(cfg.get("auto_layout")) or bool(str(cfg.get("source_entry", "")).strip())


class ScaffoldBuildPipeline:
    """Execute the five-step isolated scaffold build from blueprint config."""

    def __init__(
        self,
        logger: Optional[Logger] = None,
        verbose: bool = True,
    ) -> None:
        self._logger = logger or print
        self.verbose = verbose
        self._steps: List[str] = []

    def _step(self, number: int, title: str, detail: str = "") -> None:
        line = f"[build:{number}/{STEP_COUNT}] {title}"
        if detail:
            line = f"{line}: {detail}"
        self._steps.append(line)
        if self.verbose:
            self._logger(line)

    def run(
        self,
        context: Dict[str, Any],
        *,
        blueprint_dir: Optional[Path] = None,
        build: bool = True,
    ) -> PipelineResult:
        cfg = scaffold_config_from_context(context)
        source_entry = str(cfg.get("source_entry", "")).strip()
        if not source_entry:
            raise ValueError(
                "scaffold.source_entry is required when auto_layout is enabled "
                "or when running the isolated scaffold build pipeline"
            )

        distribution = str(cfg.get("distribution_directory", "")).strip() or None
        name = str(cfg.get("name", "")).strip() or None
        shims = list(cfg.get("compatibility_shims") or [])
        dependencies = dict(cfg.get("dependencies") or {})
        auto_layout = bool(cfg.get("auto_layout"))

        # Step 1 — resolve and validate the source entry from anywhere.
        self._step(
            1,
            "READ AND VALIDATE ABSOLUTE ENVIRONMENT PATHS",
            f"source_entry={source_entry!r}",
        )
        engine = ScaffoldEngine(
            logger=lambda msg: self._logger(f"  [scaffold] {msg}"),
            verbose=self.verbose,
        )
        try:
            from src.scaffold.source_resolver import resolve_source_entry

            entry = resolve_source_entry(source_entry, base_dir=blueprint_dir)
        except SourceEntryNotFound as exc:
            raise SourceEntryNotFound(
                f"Step 1 failed — {exc}"
            ) from exc
        self._step(
            1,
            "READ AND VALIDATE ABSOLUTE ENVIRONMENT PATHS",
            f"resolved -> {entry.path}  (language={entry.language})",
        )
        shim_label = ", ".join(shims) if shims else "(auto-detect rug/pyo3 anchors)"
        self._step(2, "RUN SANITY FILTERS AND AUTO-CORRECTION", f"shims={shim_label}")

        # Step 3 — out-of-tree workspace provisioning.
        if auto_layout and not distribution:
            self._step(
                3,
                "OUT-OF-TREE WORKSPACE PROVISIONING",
                "auto_layout=true but no distribution_directory — using temp workspace",
            )
        else:
            dest = distribution or "(system temp — auto-cleaned)"
            self._step(
                3,
                "OUT-OF-TREE WORKSPACE PROVISIONING",
                f"distribution_directory={dest}",
            )

        # Steps 4 + 5 — synthesize repo and build inside the external workspace.
        self._step(
            4,
            "SYNTHESIZE FULL REPOSITORY WORKSPACE",
            "Cargo.toml, src/lib.rs, .gitignore, test_binding.py",
        )
        if build:
            self._step(
                5,
                "EXECUTE TARGET ISOLATION BUILD",
                "cargo build --release (all artifacts stay out-of-tree)",
            )
        else:
            self._step(5, "EXECUTE TARGET ISOLATION BUILD", "skipped (--no-build)")

        try:
            result = engine.scaffold(
                source_entry=source_entry,
                name=name,
                base_dir=blueprint_dir,
                distribution_directory=Path(distribution) if distribution else None,
                dependencies=dependencies or None,
                compatibility_shims=shims if shims else None,
                build=build,
                keep=True if distribution else True,
            )
        except WorkspaceLocationError as exc:
            raise WorkspaceLocationError(
                f"Step 3 failed — {exc}"
            ) from exc

        if result.shield.get("applied"):
            self._step(
                2,
                "RUN SANITY FILTERS AND AUTO-CORRECTION",
                f"applied: {', '.join(result.shield['applied'])}",
            )

        for written in result.repo.get("files", []):
            self._logger(f"  [scaffold] + {result.workspace}/{written}")

        succeeded = True
        if build and result.build is not None:
            succeeded = bool(result.build.get("succeeded"))
            status = "succeeded" if succeeded else "failed"
            note = " (recovered after auto-correction)" if result.build.get("recovered") else ""
            self._logger(
                f"  [scaffold] build {status} in "
                f"{len(result.build.get('attempts', []))} attempt(s){note}"
            )

        return PipelineResult(succeeded=succeeded, scaffold=result, steps=list(self._steps))
