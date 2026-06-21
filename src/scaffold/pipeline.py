# -*- coding: utf-8 -*-
"""
Blueprint-driven scaffold build pipeline with first-class Language Router.

When a blueprint declares a ``[scaffold]`` section, ``python main.py build
--blueprint blueprint.aero`` routes through a five-step workflow.  Step 0 reads
``blueprint["frameworks"]["language"]`` and diverges:

* **rust**   → Cargo layout + ``cargo build --release``
* **python** → native Python layout + ``compileall`` / ``py_compile`` validation

The ``aero-universal`` tool directory is never written to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.scaffold.engine import ScaffoldEngine, ScaffoldResult
from src.scaffold.language_router import (
    build_description,
    layout_description,
    resolve_target_language,
)
from src.scaffold.source_resolver import SourceEntryNotFound, resolve_source_entry
from src.scaffold.workspace import WorkspaceLocationError

Logger = Callable[[str], None]
STEP_COUNT = 5


@dataclass
class PipelineResult:
    """Outcome of a blueprint scaffold build."""

    succeeded: bool
    scaffold: ScaffoldResult
    steps: List[str]
    language: str = "rust"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "workspace": self.scaffold.workspace,
            "language": self.language,
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
        module_mapping = dict(cfg.get("module_mapping") or {})
        decomposition_mode = str(cfg.get("decomposition_mode", "")).strip() or None
        modular = decomposition_mode == "modular_package" and bool(module_mapping)

        # Step 1 — resolve paths and route by blueprint language.
        self._step(
            1,
            "READ AND VALIDATE ABSOLUTE ENVIRONMENT PATHS",
            f"source_entry={source_entry!r}",
        )
        try:
            entry = resolve_source_entry(source_entry, base_dir=blueprint_dir)
        except SourceEntryNotFound as exc:
            raise SourceEntryNotFound(f"Step 1 failed — {exc}") from exc

        language = resolve_target_language(context, source_entry=entry)
        self._step(
            1,
            "LANGUAGE ROUTER",
            f"frameworks.language={language!r}  resolved -> {entry.path}",
        )

        engine = ScaffoldEngine(
            logger=lambda msg: self._logger(f"  [scaffold] {msg}"),
            verbose=self.verbose,
        )

        if language == "python":
            self._step(2, "RUN SANITY FILTERS AND AUTO-CORRECTION", "skipped (Python target — no Rust shims)")
        else:
            shim_label = ", ".join(shims) if shims else "(auto-detect rug/pyo3 anchors)"
            self._step(2, "RUN SANITY FILTERS AND AUTO-CORRECTION", f"shims={shim_label}")

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

        if modular:
            self._step(
                4,
                "SYNTHESIZE FULL REPOSITORY WORKSPACE",
                "decomposition_mode=modular_package — AST-split into "
                f"{', '.join(sorted(module_mapping))} + __init__.py + orchestrator",
            )
        else:
            self._step(
                4,
                "SYNTHESIZE FULL REPOSITORY WORKSPACE",
                layout_description(language),
            )
        if build:
            self._step(5, "EXECUTE TARGET ISOLATION BUILD", build_description(language))
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
                context=context,
                language=language,
                module_mapping=module_mapping or None,
                decomposition_mode=decomposition_mode,
            )
        except WorkspaceLocationError as exc:
            raise WorkspaceLocationError(f"Step 3 failed — {exc}") from exc

        if language == "rust" and result.shield.get("applied"):
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
            if language == "python":
                status = "succeeded" if succeeded else "failed"
                self._logger(f"  [scaffold] python validation {status}")
                if not succeeded and result.build.get("attempts"):
                    errors = result.build["attempts"][0].get("errors", [])
                    for err in errors:
                        self._logger(f"  [scaffold] {err}")
            else:
                status = "succeeded" if succeeded else "failed"
                note = " (recovered after auto-correction)" if result.build.get("recovered") else ""
                self._logger(
                    f"  [scaffold] build {status} in "
                    f"{len(result.build.get('attempts', []))} attempt(s){note}"
                )

        return PipelineResult(
            succeeded=succeeded,
            scaffold=result,
            steps=list(self._steps),
            language=language,
        )
