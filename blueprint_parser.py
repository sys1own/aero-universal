# -*- coding: utf-8 -*-
"""
blueprint_parser.py

Parse the monolithic `blueprint.aero` configuration and normalize it into a
runtime `build_context`. Invalid or unreadable blueprints automatically fall
back to stable coefficients from `builder_brains/build_manifest.json`.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("blueprint_parser")

_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "builder_brains", "build_manifest.json"
)
_REQUIRED_SECTIONS = ("graph", "compiler", "cortex")

# Decomposition strategies recognised in the [scaffold] block.  The empty string
# (default) means "no decomposition" — copy/optimize the single source entry.
_SUPPORTED_DECOMPOSITION_MODES = frozenset({"modular_package"})

# Optional sections introduced for large-scale physics simulation builds.
# They are fully backward compatible: a blueprint that omits them behaves
# exactly as before, falling back to the conservative defaults below.
_OPTIONAL_SECTIONS = (
    "libraries",
    "distributed",
    "gpu",
    "physics",
    "precision_shield",
    "hpc",
    "runtime",
    "frameworks",
    "validation",
    "context",
    "scaffold",
)

_ALLOWED_BLAS = {"auto", "mkl", "openblas", "none"}
_ALLOWED_MPI_FLAVORS = {"openmpi", "mpich", None}
_ALLOWED_CACHE_SHARING = {"nfs", "redis", "s3"}
_ALLOWED_GPU_BACKENDS = {"cuda", "hip", "opencl"}
_ALLOWED_FP_CONTRACT = {"allow", "disallow"}
_ALLOWED_IEEE = {"strict", "relaxed"}
_ALLOWED_SCHEDULERS = {"slurm", "pbs", "none"}
_ALLOWED_DEFAULT_FLOAT = {"double", "quad", "arbitrary"}


def _default_optional_sections() -> Dict[str, Dict[str, Any]]:
    """Conservative defaults that preserve legacy single-machine behaviour."""
    return {
        "libraries": {
            "blas": "none",
            "lapack": "none",
            "mpi": False,
            "mpi_flavor": None,
            "cuda": "none",
        },
        "distributed": {
            "enabled": False,
            "worker_nodes": [],
            "cache_sharing": "nfs",
        },
        "gpu": {
            "enabled": False,
            "backend": "cuda",
            "kernel_sources": [],
        },
        "physics": {
            "dimensions": [],
            "symbolic_validation": False,
        },
        "precision_shield": {
            "floating_point_contract": "disallow",
            "fast_math_override": False,
            "ieee_compliance": "strict",
            "default_float": "double",
            "arbitrary_precision_bits": 128,
            "per_zone_overrides": {},
            "auto_detect_need": False,
        },
        "hpc": {
            "scheduler": "none",
            "queue": "cpu",
            "nodes": 1,
            "tasks_per_node": 1,
            "walltime": "01:00:00",
            "environment": {},
            "build_on_login_node": True,
            "post_build_run": False,
        },
        "runtime": {
            "enable_feedback": False,
            "benchmark_command": "",
            "metrics_to_collect": ["wall_time"],
            "accuracy_reference": "",
            "feedback_weight": 0.3,
        },
        "frameworks": {"language": ""},
        "validation": {
            "suite": "",
            "tolerance": 1e-8,
            "test_cases": [],
            "execution_command": "",
            "validation_required": True,
        },
        "context": {"sources": []},
        "scaffold": {
            "source_entry": "",
            "auto_layout": False,
            "distribution_directory": "",
            "compatibility_shims": [],
            "name": "",
            "dependencies": {},
            "decomposition_mode": "",
            "module_mapping": {},
        },
    }


class BlueprintParseError(ValueError):
    """Raised when blueprint parsing or validation fails."""


def load_stable_manifest(manifest_path: str = _MANIFEST_PATH) -> Dict[str, Any]:
    """Load stable parameters from build_manifest.json."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.error("Failed to load fallback build_manifest.json: %s", exc)
        return {}


def detect_cycles(dependencies: Dict[str, List[str]]) -> List[str]:
    """Detect cycles in a dependency graph using DFS traversal."""
    visited: Dict[str, int] = {}
    parent: Dict[str, str] = {}

    for node in dependencies:
        visited[node] = 0

    def dfs(node: str) -> List[str]:
        visited[node] = 1
        for dependency in dependencies.get(node, []):
            if dependency not in visited:
                continue
            if visited[dependency] == 1:
                cycle = [dependency, node]
                current = node
                while current in parent and parent[current] != dependency:
                    current = parent[current]
                    cycle.append(current)
                cycle.reverse()
                return cycle
            if visited[dependency] == 0:
                parent[dependency] = node
                cycle = dfs(dependency)
                if cycle:
                    return cycle
        visited[node] = 2
        return []

    for node in dependencies:
        if visited[node] == 0:
            cycle = dfs(node)
            if cycle:
                return cycle
    return []


def parse_literal(value: str) -> Any:
    """Parse booleans, numbers, JSON literals, and plain strings."""
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned.lower() in ("true", "yes", "on"):
        return True
    if cleaned.lower() in ("false", "no", "off"):
        return False
    try:
        if "." in cleaned or "e" in cleaned.lower():
            return float(cleaned)
        return int(cleaned)
    except ValueError:
        pass
    if (
        (cleaned.startswith("[") and cleaned.endswith("]"))
        or (cleaned.startswith("{") and cleaned.endswith("}"))
        or (cleaned.startswith('"') and cleaned.endswith('"'))
    ):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if cleaned.startswith('"') and cleaned.endswith('"'):
                return cleaned[1:-1]
    return cleaned


def _coerce_dependency_map(raw_dependencies: Any) -> Dict[str, List[str]]:
    if not isinstance(raw_dependencies, dict):
        raise BlueprintParseError("[graph] dependencies must be a JSON object")

    dependency_map: Dict[str, List[str]] = {}
    for node, raw_value in raw_dependencies.items():
        node_name = str(node).strip()
        if not node_name:
            raise BlueprintParseError("[graph] dependencies contains an empty node name")
        if isinstance(raw_value, list):
            dependency_map[node_name] = [
                str(item).strip() for item in raw_value if str(item).strip()
            ]
            continue
        if isinstance(raw_value, str):
            dependency_map[node_name] = [
                item.strip() for item in raw_value.split(",") if item.strip()
            ]
            continue
        raise BlueprintParseError(
            f"[graph] dependencies for '{node_name}' must be a list or comma-separated string"
        )
    return dependency_map


def _validate_sections(sections: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    missing = [section for section in _REQUIRED_SECTIONS if section not in sections]
    if missing:
        raise BlueprintParseError(f"Missing required section(s): {', '.join(missing)}")

    graph = sections["graph"]
    if "targets" not in graph:
        raise BlueprintParseError("[graph] targets is required")
    if "dependencies" not in graph:
        raise BlueprintParseError("[graph] dependencies is required")

    targets = graph["targets"]
    if not isinstance(targets, list) or not targets:
        raise BlueprintParseError("[graph] targets must be a non-empty JSON list")

    normalized_targets: List[str] = []
    target_metadata: List[Dict[str, Any]] = []
    for target in targets:
        if isinstance(target, dict):
            target_name = str(target.get("name", "")).strip()
            if not target_name:
                raise BlueprintParseError("[graph] target objects must include a non-empty name")
            normalized_targets.append(target_name)
            target_metadata.append(dict(target))
            continue
        target_name = str(target).strip()
        if not target_name:
            raise BlueprintParseError("[graph] targets cannot contain empty values")
        normalized_targets.append(target_name)
        target_metadata.append({"name": target_name})
    graph["targets"] = normalized_targets
    graph["target_metadata"] = target_metadata

    dependency_map = _coerce_dependency_map(graph["dependencies"])
    for target in normalized_targets:
        dependency_map.setdefault(target, [])

    unknown_dependencies = sorted(
        {
            dependency
            for deps in dependency_map.values()
            for dependency in deps
            if dependency not in dependency_map
        }
    )
    if unknown_dependencies:
        raise BlueprintParseError(
            "Unknown dependency target(s): " + ", ".join(unknown_dependencies)
        )

    numeric_fields = (
        ("compiler", "tier_shifting_hotness_threshold", int),
        ("compiler", "hotspot_loop_unroll_depth", int),
        ("compiler", "pipeline_budget_seconds", (int, float)),
        ("compiler", "max_memory_mb", int),
        ("cortex", "mutation_entropy_clamp_threshold", (int, float)),
        ("cortex", "total_cooperating_agents", int),
        ("cortex", "heuristic_exploration_depth", int),
        ("cortex", "inter_core_ring_buffer_capacity", int),
    )
    for section_name, key, expected_type in numeric_fields:
        value = sections[section_name].get(key)
        if value is not None and not isinstance(value, expected_type):
            raise BlueprintParseError(f"[{section_name}] {key} has an invalid type")

    bool_fields = (
        ("graph", "allow_partial_graph"),
        ("compiler", "aot_boundary_check_elimination"),
        ("compiler", "vector_intrinsics_auto_generation"),
        ("cortex", "numa_node_locality_binding"),
    )
    for section_name, key in bool_fields:
        value = sections[section_name].get(key)
        if value is not None and not isinstance(value, bool):
            raise BlueprintParseError(f"[{section_name}] {key} must be a boolean")

    return dependency_map


def _as_bool(section: str, key: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise BlueprintParseError(f"[{section}] {key} must be a boolean")
    return value


def _as_str_list(section: str, key: str, value: Any) -> List[str]:
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise BlueprintParseError(f"[{section}] {key} must be a list or comma-separated string")


def _as_int(section: str, key: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BlueprintParseError(f"[{section}] {key} must be an integer")
    return value


def _as_float(section: str, key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlueprintParseError(f"[{section}] {key} must be a number")
    return float(value)


def _as_dict(section: str, key: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise BlueprintParseError(f"[{section}] {key} must be a JSON object")
    return dict(value)


def normalize_optional_sections(sections: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Validate and normalise the optional physics-scale sections.

    Missing sections (and missing keys) fall back to conservative defaults so
    legacy blueprints keep their original behaviour.  Present-but-invalid values
    raise :class:`BlueprintParseError`.
    """
    normalized = _default_optional_sections()

    # --- [libraries] -------------------------------------------------
    lib = sections.get("libraries")
    if isinstance(lib, dict):
        target = normalized["libraries"]
        for key in ("blas", "lapack"):
            if key in lib:
                val = str(lib[key]).strip().lower()
                if val not in _ALLOWED_BLAS:
                    raise BlueprintParseError(
                        f"[libraries] {key} must be one of {sorted(_ALLOWED_BLAS)}"
                    )
                target[key] = val
        if "mpi" in lib:
            target["mpi"] = _as_bool("libraries", "mpi", lib["mpi"])
        if "mpi_flavor" in lib:
            flavor = lib["mpi_flavor"]
            flavor = None if flavor in (None, "", "none") else str(flavor).strip().lower()
            if flavor not in _ALLOWED_MPI_FLAVORS:
                raise BlueprintParseError(
                    f"[libraries] mpi_flavor must be one of {sorted(str(f) for f in _ALLOWED_MPI_FLAVORS)}"
                )
            target["mpi_flavor"] = flavor
        if "cuda" in lib:
            target["cuda"] = str(lib["cuda"]).strip().lower()

    # --- [distributed] -----------------------------------------------
    dist = sections.get("distributed")
    if isinstance(dist, dict):
        target = normalized["distributed"]
        if "enabled" in dist:
            target["enabled"] = _as_bool("distributed", "enabled", dist["enabled"])
        if "worker_nodes" in dist:
            target["worker_nodes"] = _as_str_list("distributed", "worker_nodes", dist["worker_nodes"])
        if "cache_sharing" in dist:
            val = str(dist["cache_sharing"]).strip().lower()
            if val not in _ALLOWED_CACHE_SHARING:
                raise BlueprintParseError(
                    f"[distributed] cache_sharing must be one of {sorted(_ALLOWED_CACHE_SHARING)}"
                )
            target["cache_sharing"] = val

    # --- [gpu] -------------------------------------------------------
    gpu = sections.get("gpu")
    if isinstance(gpu, dict):
        target = normalized["gpu"]
        if "enabled" in gpu:
            target["enabled"] = _as_bool("gpu", "enabled", gpu["enabled"])
        if "backend" in gpu:
            val = str(gpu["backend"]).strip().lower()
            if val not in _ALLOWED_GPU_BACKENDS:
                raise BlueprintParseError(
                    f"[gpu] backend must be one of {sorted(_ALLOWED_GPU_BACKENDS)}"
                )
            target["backend"] = val
        if "kernel_sources" in gpu:
            target["kernel_sources"] = _as_str_list("gpu", "kernel_sources", gpu["kernel_sources"])

    # --- [physics] ---------------------------------------------------
    phys = sections.get("physics")
    if isinstance(phys, dict):
        target = normalized["physics"]
        if "dimensions" in phys:
            target["dimensions"] = _as_str_list("physics", "dimensions", phys["dimensions"])
        if "symbolic_validation" in phys:
            target["symbolic_validation"] = _as_bool(
                "physics", "symbolic_validation", phys["symbolic_validation"]
            )

    # --- [precision_shield] ------------------------------------------
    shield = sections.get("precision_shield")
    if isinstance(shield, dict):
        target = normalized["precision_shield"]
        if "floating_point_contract" in shield:
            val = str(shield["floating_point_contract"]).strip().lower()
            if val not in _ALLOWED_FP_CONTRACT:
                raise BlueprintParseError(
                    f"[precision_shield] floating_point_contract must be one of {sorted(_ALLOWED_FP_CONTRACT)}"
                )
            target["floating_point_contract"] = val
        if "fast_math_override" in shield:
            target["fast_math_override"] = _as_bool(
                "precision_shield", "fast_math_override", shield["fast_math_override"]
            )
        if "ieee_compliance" in shield:
            val = str(shield["ieee_compliance"]).strip().lower()
            if val not in _ALLOWED_IEEE:
                raise BlueprintParseError(
                    f"[precision_shield] ieee_compliance must be one of {sorted(_ALLOWED_IEEE)}"
                )
            target["ieee_compliance"] = val
        if "default_float" in shield:
            val = str(shield["default_float"]).strip().lower()
            if val not in _ALLOWED_DEFAULT_FLOAT:
                raise BlueprintParseError(
                    f"[precision_shield] default_float must be one of {sorted(_ALLOWED_DEFAULT_FLOAT)}"
                )
            target["default_float"] = val
        if "arbitrary_precision_bits" in shield:
            bits = _as_int("precision_shield", "arbitrary_precision_bits", shield["arbitrary_precision_bits"])
            if bits <= 0:
                raise BlueprintParseError("[precision_shield] arbitrary_precision_bits must be positive")
            target["arbitrary_precision_bits"] = bits
        if "per_zone_overrides" in shield:
            target["per_zone_overrides"] = _as_dict(
                "precision_shield", "per_zone_overrides", shield["per_zone_overrides"]
            )
        if "auto_detect_need" in shield:
            target["auto_detect_need"] = _as_bool(
                "precision_shield", "auto_detect_need", shield["auto_detect_need"]
            )

    # --- [hpc] -------------------------------------------------------
    hpc = sections.get("hpc")
    if isinstance(hpc, dict):
        target = normalized["hpc"]
        if "scheduler" in hpc:
            val = str(hpc["scheduler"]).strip().lower()
            if val not in _ALLOWED_SCHEDULERS:
                raise BlueprintParseError(
                    f"[hpc] scheduler must be one of {sorted(_ALLOWED_SCHEDULERS)}"
                )
            target["scheduler"] = val
        if "queue" in hpc:
            target["queue"] = str(hpc["queue"]).strip()
        if "nodes" in hpc:
            target["nodes"] = _as_int("hpc", "nodes", hpc["nodes"])
        if "tasks_per_node" in hpc:
            target["tasks_per_node"] = _as_int("hpc", "tasks_per_node", hpc["tasks_per_node"])
        if "walltime" in hpc:
            target["walltime"] = str(hpc["walltime"]).strip()
        if "environment" in hpc:
            target["environment"] = _as_dict("hpc", "environment", hpc["environment"])
        if "build_on_login_node" in hpc:
            target["build_on_login_node"] = _as_bool("hpc", "build_on_login_node", hpc["build_on_login_node"])
        if "post_build_run" in hpc:
            target["post_build_run"] = _as_bool("hpc", "post_build_run", hpc["post_build_run"])

    # --- [runtime] ---------------------------------------------------
    runtime = sections.get("runtime")
    if isinstance(runtime, dict):
        target = normalized["runtime"]
        if "enable_feedback" in runtime:
            target["enable_feedback"] = _as_bool("runtime", "enable_feedback", runtime["enable_feedback"])
        if "benchmark_command" in runtime:
            target["benchmark_command"] = str(runtime["benchmark_command"])
        if "metrics_to_collect" in runtime:
            target["metrics_to_collect"] = _as_str_list("runtime", "metrics_to_collect", runtime["metrics_to_collect"])
        if "accuracy_reference" in runtime:
            target["accuracy_reference"] = str(runtime["accuracy_reference"])
        if "feedback_weight" in runtime:
            weight = _as_float("runtime", "feedback_weight", runtime["feedback_weight"])
            if not 0.0 <= weight <= 1.0:
                raise BlueprintParseError("[runtime] feedback_weight must be between 0 and 1")
            target["feedback_weight"] = weight

    # --- [frameworks] ------------------------------------------------
    frameworks = sections.get("frameworks")
    if isinstance(frameworks, dict):
        target = normalized["frameworks"]
        if "language" in frameworks:
            lang = str(frameworks["language"]).strip().lower()
            if lang and lang not in ("rust", "python"):
                raise BlueprintParseError("[frameworks] language must be 'rust' or 'python'")
            target["language"] = lang
        framework_map: Dict[str, Any] = dict(target)
        for name, spec in frameworks.items():
            if name == "language":
                continue
            if not isinstance(spec, dict):
                raise BlueprintParseError(f"[frameworks] '{name}' must be a JSON object")
            framework_map[str(name)] = dict(spec)
        normalized["frameworks"] = framework_map

    # --- [validation] ------------------------------------------------
    validation = sections.get("validation")
    if isinstance(validation, dict):
        target = normalized["validation"]
        if "suite" in validation:
            target["suite"] = str(validation["suite"])
        if "tolerance" in validation:
            target["tolerance"] = _as_float("validation", "tolerance", validation["tolerance"])
        if "test_cases" in validation:
            target["test_cases"] = _as_str_list("validation", "test_cases", validation["test_cases"])
        if "execution_command" in validation:
            target["execution_command"] = str(validation["execution_command"])
        if "validation_required" in validation:
            target["validation_required"] = _as_bool("validation", "validation_required", validation["validation_required"])

    # --- [context] ---------------------------------------------------
    context = sections.get("context")
    if context is not None:
        if isinstance(context, list):
            sources = [dict(s) for s in context if isinstance(s, dict)]
            normalized["context"] = {"sources": sources}
        elif isinstance(context, dict):
            raw_sources = context.get("sources", [])
            if not isinstance(raw_sources, list):
                raise BlueprintParseError("[context] sources must be a list")
            merged = {k: v for k, v in context.items() if k != "sources"}
            merged["sources"] = [dict(s) for s in raw_sources if isinstance(s, dict)]
            normalized["context"] = merged
        else:
            raise BlueprintParseError("[context] must be a JSON object or list")

    # --- [scaffold] --------------------------------------------------
    scaffold = sections.get("scaffold")
    if isinstance(scaffold, dict):
        target = normalized["scaffold"]
        if "source_entry" in scaffold:
            target["source_entry"] = str(scaffold["source_entry"]).strip()
        if "auto_layout" in scaffold:
            target["auto_layout"] = _as_bool("scaffold", "auto_layout", scaffold["auto_layout"])
        if "distribution_directory" in scaffold:
            target["distribution_directory"] = str(scaffold["distribution_directory"]).strip()
        if "name" in scaffold:
            target["name"] = str(scaffold["name"]).strip()
        if "compatibility_shims" in scaffold:
            target["compatibility_shims"] = _as_str_list(
                "scaffold", "compatibility_shims", scaffold["compatibility_shims"]
            )
        if "dependencies" in scaffold:
            target["dependencies"] = _as_dict("scaffold", "dependencies", scaffold["dependencies"])
        if "decomposition_mode" in scaffold:
            mode = str(scaffold["decomposition_mode"]).strip()
            if mode and mode not in _SUPPORTED_DECOMPOSITION_MODES:
                raise BlueprintParseError(
                    "[scaffold] decomposition_mode must be one of "
                    f"{sorted(_SUPPORTED_DECOMPOSITION_MODES)} (got {mode!r})"
                )
            target["decomposition_mode"] = mode
        if "module_mapping" in scaffold:
            raw_mapping = _as_dict("scaffold", "module_mapping", scaffold["module_mapping"])
            mapping: Dict[str, List[str]] = {}
            for key, value in raw_mapping.items():
                filename = str(key).strip()
                if not filename:
                    raise BlueprintParseError(
                        "[scaffold] module_mapping keys must be non-empty target filenames"
                    )
                mapping[filename] = _as_str_list(
                    "scaffold", f"module_mapping.{filename}", value
                )
            target["module_mapping"] = mapping

    return normalized


# Sections a JSON blueprint must declare (feature: full multi-tool blueprint).
_JSON_REQUIRED_SECTIONS = (
    "project",
    "analysis",
    "precision_shield",
    "hardware_profiling",
    "memoization",
    "context",
    "frameworks",
    "runtime",
    "validation",
    "physics",
)


def looks_like_json(content: str) -> bool:
    """Return True if the blueprint content is JSON (starts with ``{``)."""
    stripped = content.lstrip()
    return stripped.startswith("{")


def parse_json_blueprint(content: str) -> Dict[str, Any]:
    """Parse and validate a JSON ``blueprint.aero``.

    Validates that every required section is present (with a clear error
    message), fills in conservative defaults for any optional section that is
    absent, and returns a normalised ``build_context`` the engines can consume
    directly.  Unknown keys inside a present section are preserved (e.g.
    ``precision_shield.shield_zones``).
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise BlueprintParseError(f"Invalid JSON blueprint: {exc}") from exc
    if not isinstance(data, dict):
        raise BlueprintParseError("JSON blueprint must be an object")

    missing = [section for section in _JSON_REQUIRED_SECTIONS if section not in data]
    if missing:
        raise BlueprintParseError(
            "JSON blueprint missing required section(s): " + ", ".join(missing)
        )

    context: Dict[str, Any] = dict(data)
    # Fill in defaults for any optional section that is entirely absent, without
    # clobbering sections the user provided.
    for key, default in _default_optional_sections().items():
        context.setdefault(key, default)

    context["workspace_status"] = "stable_active"
    context["blueprint_format"] = "json"
    context["timestamp"] = time.time()
    return context


def parse_blueprint_content(content: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    """Parse blueprint content and validate the monolithic schema."""
    sections: Dict[str, Dict[str, Any]] = {}
    current_section: Optional[str] = None

    for idx, raw_line in enumerate(content.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if not current_section:
                raise BlueprintParseError(f"Line {idx}: Empty section header")
            if current_section in sections:
                raise BlueprintParseError(f"Line {idx}: Duplicate section [{current_section}]")
            sections[current_section] = {}
            continue

        if "=" in line or ":" in line:
            if current_section is None:
                raise BlueprintParseError(f"Line {idx}: Key-value pair found before any section")
            separator = "=" if "=" in line else ":"
            key, value = line.split(separator, 1)
            normalized_key = key.strip()
            if not normalized_key:
                raise BlueprintParseError(f"Line {idx}: Empty key")
            sections[current_section][normalized_key] = parse_literal(value)
            continue

        raise BlueprintParseError(f"Line {idx}: Unrecognized layout structure: {line}")

    dependencies = _validate_sections(sections)
    normalize_optional_sections(sections)  # validate optional sections if present
    cycle = detect_cycles(dependencies)
    if cycle:
        raise BlueprintParseError(f"Invalid instruction loop detected: {' -> '.join(cycle)}")
    return sections, dependencies


def create_fallback_context(manifest: Dict[str, Any], error_msg: str) -> Dict[str, Any]:
    """Generate a stable fallback build_context from manifest values."""
    logger.warning("Reverting to last known stable build manifest state: %s", error_msg)

    weights = manifest.get("hyperparameter_weights", {})
    tuner_params = weights.get("parameter_tuner", {})
    scheduler_params = manifest.get("execution_cost_ceilings", {})
    parameters = manifest.get("parameters", {})

    build_context = {
        "workspace_status": "reverted_fallback",
        "fallback_reason": error_msg,
        "timestamp": time.time(),
        "compilation_targets": ["scanner", "decision_tree", "parameter_tuner"],
        "dependency_matrix": {},
        "active_optimizer_flags": {
            "profile_guided_optimization": "enabled_strict",
            "tier_shifting_hotness_threshold": 100,
            "hotspot_loop_unroll_depth": 32,
            "aot_boundary_check_elimination": True,
            "vector_intrinsics_auto_generation": True,
            "consensus_protocol": "raft_driven_mutation_lock",
            "mutation_entropy_clamp_threshold": float(tuner_params.get("mutation_sigma", 0.05)),
        },
        "environment_targets": {
            "execution_mode": "lock_free_polling_wheel_realtime",
            "core_affinity_mask": "0xFFFF",
            "numa_node_locality_binding": True,
            "inter_core_ring_buffer_capacity": 262144,
        },
        "resource_metrics": {
            "pipeline_budget_seconds": float(
                scheduler_params.get("total_pipeline_budget_seconds", 120.0)
            ),
            "max_memory_mb": int(scheduler_params.get("max_memory_mb", 2048)),
            "elapsed_seconds": {},
        },
        "node_configurations": {},
        "graph": {
            "entrypoint": "orchestrator",
            "targets": ["scanner", "decision_tree", "parameter_tuner"],
            "dependencies": {
                "scanner": [],
                "decision_tree": ["scanner"],
                "parameter_tuner": ["decision_tree"],
            },
            "workspace_mode": "fallback_manifest",
            "allow_partial_graph": False,
        },
    }
    build_context.update(_default_optional_sections())

    for key, value in parameters.items():
        if key.startswith("tuned_"):
            build_context["active_optimizer_flags"][key.replace("tuned_", "")] = value

    return build_context


def _looks_like_lean(content: str) -> bool:
    """Detect the ultra-lean Invisible Configuration dialect (lazy import)."""
    from src.invisible_config.lean_parser import looks_like_lean_blueprint

    return looks_like_lean_blueprint(content)


def _parse_lean_blueprint(content: str, project_root: str) -> Dict[str, Any]:
    """Infer a full build_context from a lean blueprint (lazy import)."""
    from pathlib import Path

    from src.invisible_config.engine import InvisibleConfigEngine

    return InvisibleConfigEngine(Path(project_root)).build_context_from_source(content)


def parse_dsl_blueprint(content: str, filename: str = "blueprint.aero") -> Dict[str, Any]:
    """Parse a block-DSL ``blueprint.aero`` and return a normalized ``build_context``.

    Validation errors are raised (via :mod:`blueprint_lang`) so misconfigured
    DSL blueprints get clear diagnostics rather than a silent fallback.
    """
    import blueprint_lang
    from build_graph import blueprint_to_dag

    blueprint = blueprint_lang.load_source(content, filename)
    graph = blueprint_to_dag(blueprint)
    context = graph.to_build_context()

    context["workspace_status"] = "stable_active"
    context["blueprint_format"] = "dsl"
    context["timestamp"] = time.time()
    context["active_optimizer_flags"] = {
        "profile_guided_optimization": "enabled_strict",
        "tier_shifting_hotness_threshold": 100,
        "hotspot_loop_unroll_depth": 32,
        "aot_boundary_check_elimination": True,
        "vector_intrinsics_auto_generation": True,
        "consensus_protocol": "raft_driven_mutation_lock",
        "mutation_entropy_clamp_threshold": 0.05,
    }
    context["environment_targets"] = {
        "execution_mode": "lock_free_polling_wheel_realtime",
        "core_affinity_mask": "0xFFFF",
        "numa_node_locality_binding": True,
        "inter_core_ring_buffer_capacity": 262144,
    }
    context["resource_metrics"] = {
        "pipeline_budget_seconds": 120.0,
        "max_memory_mb": 2048,
        "elapsed_seconds": {target: 0.0 for target in context["compilation_targets"]},
    }
    context["node_configurations"] = {}
    context.update(_default_optional_sections())
    return context


def parse_blueprint(blueprint_path: str, manifest_path: str = _MANIFEST_PATH) -> Dict[str, Any]:
    """Load blueprint.aero, validate it, and generate a normalized build_context."""
    stable_manifest = load_stable_manifest(manifest_path)

    if not os.path.exists(blueprint_path):
        return create_fallback_context(
            stable_manifest, f"Blueprint file not found at: {blueprint_path}"
        )

    with open(blueprint_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    # The ultra-lean "Invisible Configuration Layer" dialect: a handful of lines
    # of semantic intent from which the whole build graph is inferred by
    # scanning the project directory.  Detected before JSON/INI so it routes to
    # the DAG-inference engine instead of the legacy parsers.
    if _looks_like_lean(content):
        try:
            return _parse_lean_blueprint(content, os.path.dirname(os.path.abspath(blueprint_path)))
        except Exception as exc:  # noqa: BLE001 - fall back to stable manifest
            logger.exception("Lean blueprint inference failed for %s", blueprint_path)
            return create_fallback_context(stable_manifest, f"Lean blueprint inference failed: {exc}")

    # JSON blueprints take a dedicated, strict path: validation errors are
    # surfaced (raised) rather than silently falling back, so misconfigured
    # JSON is reported clearly.  INI blueprints keep the original fallback
    # behaviour for backward compatibility.
    if looks_like_json(content):
        return parse_json_blueprint(content)

    # Block-DSL blueprints are parsed/validated via blueprint_lang and
    # converted into the engine's build_context via build_graph.
    import blueprint_lang
    if blueprint_lang.looks_like_blueprint_dsl(content):
        return parse_dsl_blueprint(content, blueprint_path)

    try:
        sections, dependencies = parse_blueprint_content(content)
        graph_section = sections["graph"]
        compiler_section = sections["compiler"]
        cortex_section = sections["cortex"]
        optional_sections = normalize_optional_sections(sections)

        context = {
            "workspace_status": "stable_active",
            "timestamp": time.time(),
            "compilation_targets": graph_section["targets"],
            "dependency_matrix": dependencies,
            "active_optimizer_flags": {
                "profile_guided_optimization": compiler_section.get(
                    "profile_guided_optimization", "enabled_strict"
                ),
                "tier_shifting_hotness_threshold": compiler_section.get(
                    "tier_shifting_hotness_threshold", 100
                ),
                "hotspot_loop_unroll_depth": compiler_section.get(
                    "hotspot_loop_unroll_depth", 32
                ),
                "aot_boundary_check_elimination": compiler_section.get(
                    "aot_boundary_check_elimination", True
                ),
                "vector_intrinsics_auto_generation": compiler_section.get(
                    "vector_intrinsics_auto_generation", True
                ),
                "consensus_protocol": cortex_section.get(
                    "consensus_protocol", "raft_driven_mutation_lock"
                ),
                "mutation_entropy_clamp_threshold": cortex_section.get(
                    "mutation_entropy_clamp_threshold", 0.05
                ),
            },
            "environment_targets": {
                "execution_mode": cortex_section.get(
                    "execution_mode", "lock_free_polling_wheel_realtime"
                ),
                "core_affinity_mask": cortex_section.get("core_affinity_mask", "0xFFFF"),
                "numa_node_locality_binding": cortex_section.get(
                    "numa_node_locality_binding", True
                ),
                "inter_core_ring_buffer_capacity": cortex_section.get(
                    "inter_core_ring_buffer_capacity", 262144
                ),
            },
            "resource_metrics": {
                "pipeline_budget_seconds": float(
                    compiler_section.get("pipeline_budget_seconds", 120.0)
                ),
                "max_memory_mb": int(compiler_section.get("max_memory_mb", 2048)),
                "elapsed_seconds": {
                    target: 0.0 for target in graph_section["targets"]
                },
            },
            "node_configurations": {},
            "graph": {
                "entrypoint": graph_section.get("entrypoint", "orchestrator"),
                "targets": graph_section["targets"],
                "target_metadata": graph_section.get("target_metadata", []),
                "dependencies": dependencies,
                "workspace_mode": graph_section.get("workspace_mode", "incremental"),
                "allow_partial_graph": graph_section.get("allow_partial_graph", False),
            },
        }
        context.update(optional_sections)
        return context
    except Exception as exc:
        logger.exception("Blueprint parsing failed for %s", blueprint_path)
        return create_fallback_context(stable_manifest, f"Parser failure: {exc}")