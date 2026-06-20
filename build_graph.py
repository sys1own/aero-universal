# -*- coding: utf-8 -*-
"""Map ``blueprint.aero`` target blocks to an internal DAG and resolve build order.

The module bridges two worlds:

* **blueprint_lang** -- the block-DSL parser that yields a validated
  :class:`~blueprint_lang.nodes.Blueprint` AST with ``target`` blocks and
  ``requires`` dependency arrays.
* **The orchestrator's DAG** -- a flat ``{name: [deps]}`` dependency matrix
  consumed by the existing build engine.

Public API
----------
* :func:`blueprint_to_dag` -- convert a :class:`Blueprint` into a
  :class:`BuildGraph`.
* :class:`BuildGraph` -- holds the resolved topological order and can
  render a clean, minimalist visual tree of the planned build steps.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from blueprint_lang.nodes import Blueprint, ListValue, StringValue


@dataclass
class TargetNode:
    """A single build target extracted from the blueprint AST."""

    name: str
    language: str
    sources: List[str]
    requires: List[str]
    flags: List[str] = field(default_factory=list)
    defines: List[str] = field(default_factory=list)
    output: Optional[str] = None
    optional: bool = False
    # Rust/Cargo: point at a crate in a subdirectory and/or an explicit manifest.
    manifest_path: Optional[str] = None
    root: Optional[str] = None
    # Pin dependency versions for a synthesised manifest ("name=version" entries).
    cargo_dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "language": self.language,
            "sources": self.sources,
            "requires": self.requires,
        }
        if self.flags:
            d["flags"] = self.flags
        if self.defines:
            d["defines"] = self.defines
        if self.output:
            d["output"] = self.output
        if self.optional:
            d["optional"] = True
        if self.manifest_path:
            d["manifest_path"] = self.manifest_path
        if self.root:
            d["root"] = self.root
        if self.cargo_dependencies:
            d["cargo_dependencies"] = self.cargo_dependencies
        return d


@dataclass
class BuildGraph:
    """Resolved build DAG with topological ordering and rendering helpers."""

    targets: Dict[str, TargetNode]
    dependency_map: Dict[str, List[str]]
    build_order: List[str]
    project_name: Optional[str] = None
    project_version: Optional[str] = None

    # -- queries -----------------------------------------------------------

    @property
    def levels(self) -> List[List[str]]:
        """Group targets into parallel build levels (Kahn's layers)."""
        in_degree: Dict[str, int] = {name: 0 for name in self.targets}
        for deps in self.dependency_map.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0)

        # Re-compute in-degree from the dependency map (reverse direction).
        in_degree = {name: 0 for name in self.targets}
        for name, deps in self.dependency_map.items():
            for dep in deps:
                pass  # deps are what `name` depends ON, not who depends on it
        # in-degree: count how many targets list `name` as a dependency
        reverse: Dict[str, List[str]] = {name: [] for name in self.targets}
        for name, deps in self.dependency_map.items():
            for dep in deps:
                if dep in reverse:
                    reverse[dep].append(name)

        in_degree = {name: len(self.dependency_map.get(name, [])) for name in self.targets}
        layers: List[List[str]] = []
        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        while queue:
            layer = sorted(queue)
            layers.append(layer)
            next_queue: deque[str] = deque()
            for name in layer:
                for dependent in reverse.get(name, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)
            queue = next_queue
        return layers

    def dependents_of(self, name: str) -> List[str]:
        """Return targets that directly depend on *name*."""
        return [
            t for t, deps in self.dependency_map.items()
            if name in deps
        ]

    # -- rendering ---------------------------------------------------------

    def render_tree(self) -> str:
        """Render a minimalist visual tree of the planned build steps."""
        lines: List[str] = []

        header = "Build Plan"
        if self.project_name:
            header += f": {self.project_name}"
            if self.project_version:
                header += f" v{self.project_version}"
        lines.append(header)
        lines.append("=" * len(header))

        levels = self.levels
        total = len(self.build_order)
        step = 0
        for level_idx, level in enumerate(levels):
            is_last_level = level_idx == len(levels) - 1
            for target_idx, name in enumerate(level):
                step += 1
                node = self.targets[name]
                deps = self.dependency_map.get(name, [])

                is_last_in_level = target_idx == len(level) - 1
                is_last = is_last_level and is_last_in_level

                connector = "└── " if is_last else "├── "
                continuation = "    " if is_last else "│   "

                tag = f"[{node.language}]"
                opt = " (optional)" if node.optional else ""
                lines.append(f"{connector}{step}. {name} {tag}{opt}")

                if deps:
                    lines.append(f"{continuation}requires: {', '.join(deps)}")

                src_count = len(node.sources)
                src_label = f"{src_count} source pattern{'s' if src_count != 1 else ''}"
                lines.append(f"{continuation}sources:  {src_label}")

                if node.output:
                    lines.append(f"{continuation}output:   {node.output}")

        lines.append("")
        lines.append(f"{total} target{'s' if total != 1 else ''}, "
                      f"{len(levels)} stage{'s' if len(levels) != 1 else ''}")
        return "\n".join(lines)

    # -- export to build_context -------------------------------------------

    def to_build_context(self) -> Dict[str, Any]:
        """Lower the graph into the ``build_context`` dict the engine expects."""
        target_names = self.build_order
        target_metadata = [self.targets[n].to_dict() for n in target_names]

        return {
            "compilation_targets": target_names,
            "dependency_matrix": dict(self.dependency_map),
            "graph": {
                "entrypoint": "orchestrator",
                "targets": target_names,
                "target_metadata": target_metadata,
                "dependencies": dict(self.dependency_map),
                "workspace_mode": "incremental",
                "allow_partial_graph": False,
            },
        }


def _extract_string_list(block, key: str) -> List[str]:
    """Extract a list-of-strings field from a block, returning [] if absent."""
    fld = block.get(key)
    if fld is None:
        return []
    val = fld.value
    if isinstance(val, ListValue):
        return [item.value for item in val.items if isinstance(item, StringValue)]
    return []


def _extract_string(block, key: str, default: str = "") -> str:
    fld = block.get(key)
    if fld is None:
        return default
    val = fld.value
    if isinstance(val, StringValue):
        return val.value
    return default


def _extract_bool(block, key: str, default: bool = False) -> bool:
    fld = block.get(key)
    if fld is None:
        return default
    val = fld.value
    if hasattr(val, "value") and isinstance(val.value, bool):
        return val.value
    return default


def _topological_sort(dep_map: Dict[str, List[str]]) -> List[str]:
    """Kahn's algorithm -- assumes the graph is acyclic (validated upstream)."""
    in_degree: Dict[str, int] = {name: 0 for name in dep_map}
    for deps in dep_map.values():
        for dep in deps:
            if dep in in_degree:
                pass  # counted below
    # Build in-degree from the dep_map: in_degree[X] = how many deps X has
    # But for topological sort we need: in_degree[X] = how many targets list X as a dep
    # Wait, dep_map[X] = [things X depends on], so for topo sort:
    #   in_degree[X] = len(dep_map[X])  -- wrong, that's out-degree in reverse.
    # Actually for Kahn's: in_degree of a node = number of edges pointing TO it.
    # An edge from A -> B means "B depends on A", or equivalently, dep_map[B] contains A.
    # So in_degree[A] = count of nodes B where A ∈ dep_map[B]... no wait.
    # dep_map[B] = [A] means B depends on A, meaning A must come first.
    # The DAG edge is A -> B (A before B).
    # in_degree[B] = number of prerequisites of B = len(dep_map[B]).

    in_degree = {name: len(deps) for name, deps in dep_map.items()}
    queue = deque(sorted(name for name, deg in in_degree.items() if deg == 0))
    order: List[str] = []

    # reverse adjacency: who depends on me?
    reverse: Dict[str, List[str]] = {name: [] for name in dep_map}
    for name, deps in dep_map.items():
        for dep in deps:
            if dep in reverse:
                reverse[dep].append(name)

    while queue:
        node = queue.popleft()
        order.append(node)
        for dependent in sorted(reverse.get(node, [])):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    return order


def blueprint_to_dag(blueprint: Blueprint) -> BuildGraph:
    """Convert a validated :class:`Blueprint` AST into a :class:`BuildGraph`.

    The blueprint must already be validated (via :func:`blueprint_lang.load_source`
    or :func:`blueprint_lang.load_file`) so the ``requires`` graph is guaranteed
    to be acyclic and all referenced targets exist.
    """
    targets: Dict[str, TargetNode] = {}
    dep_map: Dict[str, List[str]] = {}

    for block in blueprint.targets:
        requires = _extract_string_list(block, "requires")
        node = TargetNode(
            name=block.name,
            language=_extract_string(block, "language"),
            sources=_extract_string_list(block, "sources"),
            requires=requires,
            flags=_extract_string_list(block, "flags"),
            defines=_extract_string_list(block, "defines"),
            output=_extract_string(block, "output") or None,
            optional=_extract_bool(block, "optional"),
            manifest_path=_extract_string(block, "manifest_path") or None,
            root=_extract_string(block, "root") or None,
            cargo_dependencies=_extract_string_list(block, "cargo_dependencies"),
        )
        targets[node.name] = node
        dep_map[node.name] = requires

    build_order = _topological_sort(dep_map)

    project_name: Optional[str] = None
    project_version: Optional[str] = None
    if blueprint.projects:
        proj = blueprint.projects[0]
        project_name = proj.name
        version_fld = proj.get("version")
        if version_fld and isinstance(version_fld.value, StringValue):
            project_version = version_fld.value.value

    return BuildGraph(
        targets=targets,
        dependency_map=dep_map,
        build_order=build_order,
        project_name=project_name,
        project_version=project_version,
    )
