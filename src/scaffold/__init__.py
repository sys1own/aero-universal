# -*- coding: utf-8 -*-
"""
Zero-config, out-of-tree standalone repository generator.

Resolves a ``source_entry`` from anywhere on the filesystem, shields rug/pyo3
sources with the codified compatibility fixes, and emits a complete, turn-key
Rust/pyo3 project (``Cargo.toml`` / ``src/lib.rs`` / ``.gitignore`` /
``README.md`` / ``test_binding.py``) into an out-of-tree workspace -- keeping the
``aero-universal`` directory completely clean.

Typical use::

    from src.scaffold import ScaffoldEngine

    engine = ScaffoldEngine(logger=print, verbose=True)
    result = engine.scaffold("/content/lib.rs", distribution_directory="~/out/anyon")
"""

from src.scaffold.engine import ScaffoldEngine, ScaffoldResult
from src.scaffold.recovery import DiagnosticRecoveryRunner, RecoveryResult
from src.scaffold.repo_generator import (
    GeneratedRepo,
    RepoSpec,
    build_spec,
    generate_repo,
    infer_dependencies,
)
from src.scaffold.rust_shield import EXTENSION_TRAITS, RUST_ANCHORS, RustSemanticShield, ShieldReport
from src.scaffold.source_resolver import (
    SourceEntry,
    SourceEntryNotFound,
    resolve_source_entry,
)
from src.scaffold.workspace import OutOfTreeWorkspace, WorkspaceLocationError

__all__ = [
    "ScaffoldEngine",
    "ScaffoldResult",
    "RustSemanticShield",
    "ShieldReport",
    "EXTENSION_TRAITS",
    "RUST_ANCHORS",
    "OutOfTreeWorkspace",
    "WorkspaceLocationError",
    "RepoSpec",
    "GeneratedRepo",
    "build_spec",
    "generate_repo",
    "infer_dependencies",
    "SourceEntry",
    "SourceEntryNotFound",
    "resolve_source_entry",
    "DiagnosticRecoveryRunner",
    "RecoveryResult",
]

__version__ = "1.0.0"
