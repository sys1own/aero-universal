from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

import orchestrator

_BLUEPRINT_CONFIG = Path(__file__).resolve().parent / "blueprint_config.json"


def _load_blueprint_config(path: Optional[str] = None) -> dict:
    p = Path(path) if path else _BLUEPRINT_CONFIG
    if not p.exists():
        print(f"Blueprint config not found: {p}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------
# Subcommand handlers
# ------------------------------------------------------------------


def _strict_blueprint_gate(workspace: Path) -> Optional[int]:
    """Strictly validate a block-format ``blueprint.aero`` before any build step.

    Returns an exit code to abort with, or ``None`` to proceed.  This is a no-op
    for the legacy INI/JSON blueprint formats (which keep their existing
    fallback behaviour); it only engages for the declarative block DSL handled by
    :mod:`blueprint_lang`, where a syntax/validation error must abort the run with
    a precise, user-friendly message before anything is built.
    """
    import blueprint_lang

    bp_path = workspace / "blueprint.aero"
    if not bp_path.exists():
        return None
    try:
        source = bp_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not blueprint_lang.looks_like_blueprint_dsl(source):
        return None
    error = blueprint_lang.check_source(source, filename=str(bp_path))
    if error is None:
        return None
    print(error, file=sys.stderr)
    print(
        "\nAborting: blueprint.aero failed strict validation; no build steps were run.",
        file=sys.stderr,
    )
    return 2


def build_command(args: argparse.Namespace) -> int:
    import blueprint_parser

    orchestrator.configure_logging(verbose=args.verbose)
    workspace = Path(args.workspace).resolve()

    # Strict syntax/validation gate -- runs BEFORE any build step so a broken
    # block-format blueprint aborts immediately with a clear diagnostic.
    gate = _strict_blueprint_gate(workspace)
    if gate is not None:
        return gate

    context = blueprint_parser.parse_blueprint(str(workspace / "blueprint.aero"))

    # --validation-only: skip the build entirely and just run the suite.
    if getattr(args, "validation_only", False):
        return _run_validation_stage(context, workspace)

    # Context ingestion runs before the build so imported sources are present.
    _run_ingestion_stage(context, workspace)

    # Domain-agnostic semantic fluidity: ingest unstructured context into the
    # Invariant Schema, exposed to code generator nodes as a compilation input.
    _maybe_run_semantic_fluidity(workspace)

    # Hardware profiling at the start of the build cycle (feature #6).
    if not getattr(args, "no_hardware_probe", False):
        _maybe_hardware_probe(workspace)

    # HPC integration: optionally submit the build to a cluster (feature #1).
    ran_on_cluster = False
    if not getattr(args, "no_hpc", False):
        ran_on_cluster = _maybe_submit_hpc_build(context, workspace, args)

    if not ran_on_cluster:
        metadata = orchestrator.run_build(
            workspace_root=str(workspace),
            cycles=args.cycles,
            telemetry_interval=args.telemetry_interval,
        )
        print()
        print("Build completed successfully.")
        print(f"Manifest: {metadata.get('manifest_path')}")
        for asset in metadata.get("applied_assets", []):
            print(f"Updated asset: {asset}")

    # Autonomous Hardware-Polymerization: probe the host and polymorphically
    # rewrite the freshly generated sources for it, after code generation but
    # before any linking/execution.  Runs transparently with no user flags.
    if not getattr(args, "no_polymorph", False):
        _maybe_run_polymorphization(workspace)

    # Self-evolution after the initial build (feature #5).
    if not getattr(args, "no_evolution", False):
        _maybe_run_evolution(workspace)

    # Runtime feedback after the build (feature #3).
    if getattr(args, "runtime_feedback", False) or context.get("runtime", {}).get("enable_feedback"):
        _run_runtime_stage(context, workspace)

    # Validation gatekeeper (feature #5).
    return _run_validation_stage(context, workspace)


def _workspace_json_config(workspace: Path) -> dict:
    """Load ``blueprint_config.json`` from the workspace if present, else {}."""
    path = workspace / "blueprint_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run_ingestion_stage(context: dict, workspace: Path) -> None:
    # Context may be declared in blueprint.aero (INI) or blueprint_config.json.
    sources = (context.get("context", {}) or {}).get("sources", [])
    config = context
    if not sources:
        json_cfg = _workspace_json_config(workspace)
        sources = (json_cfg.get("context", {}) or {}).get("sources", [])
        config = json_cfg
    if not sources:
        return
    from src.context.ingest import ContextIngestor

    print(f"\n[context] ingesting {len(sources)} source tree(s)...")
    try:
        report = ContextIngestor(config, workspace).ingest_all()
        print(f"[context] ingested {report['files_ingested']} file(s), "
              f"repaired {report['files_repaired']}, errors {len(report['errors'])}")
    except Exception as exc:  # noqa: BLE001 - ingestion must not abort the build
        print(f"[context] ingestion failed: {exc}")


def _maybe_run_semantic_fluidity(workspace: Path) -> None:
    """Ingest unstructured context (papers, prose, code) into the Invariant
    Schema and write it to the workspace as a high-level compilation input for
    downstream code generator nodes.  Opt-in via blueprint_config.json's
    ``semantic_fluidity`` section; never aborts the build on failure.
    """
    config = _workspace_json_config(workspace)
    fluidity_cfg = config.get("semantic_fluidity", {})
    if not fluidity_cfg.get("enabled"):
        return
    source_dir = workspace / fluidity_cfg.get("source_dir", "context_sources")
    if not source_dir.exists():
        return
    from src.semantic_fluidity import ContextIngestionEngine

    print(f"\n[semantic-fluidity] ingesting {source_dir}...")
    try:
        engine = ContextIngestionEngine()
        output_path = workspace / ContextIngestionEngine.REPORT_NAME
        payload = engine.ingest_and_export(source_dir, output_path)
        schema = payload["invariant_schema"]
        print(
            f"[semantic-fluidity] {len(schema['domains'])} domain(s), "
            f"{len(schema['state_variables'])} state var(s), "
            f"{len(schema['equations'])} equation(s), "
            f"{len(schema['boundaries'])} boundary rule(s) -> {output_path}"
        )
    except Exception as exc:  # noqa: BLE001 - ingestion must not abort the build
        print(f"[semantic-fluidity] ingestion skipped: {exc}")


def _maybe_run_polymorphization(workspace: Path) -> None:
    """Probe the host and polymorphically rewrite the generated sources for it.

    Runs after code generation but before linking/execution.  Operates on the
    generated artifacts directory and writes rewritten copies into an ephemeral
    build cache (``.aero/polymorph_cache``), leaving the user's primary source
    directory untouched.  On by default (no flags required); can be disabled via
    ``--no-polymorph`` or ``blueprint_config.json``'s ``polymorphization`` section.
    Never aborts the build on failure.
    """
    config = _workspace_json_config(workspace)
    poly_cfg = config.get("polymorphization", {})
    if poly_cfg.get("enabled") is False:
        return
    source_dir = workspace / poly_cfg.get("source_dir", "build_artifacts")
    if not source_dir.exists():
        return
    from src.polymorphization import PolymorphizationEngine

    cache_dir = workspace / poly_cfg.get("cache_dir", str(Path(".aero") / "polymorph_cache"))
    print(f"\n[polymorph] inspecting host and rewriting {source_dir}...")
    try:
        engine = PolymorphizationEngine()
        report = engine.polymerize_tree(source_dir, cache_dir)
        engine.write_report(report, cache_dir)
        topo = report["topology"]
        derived = topo["derived"]
        rewrite = report["rewrite"]
        print(
            f"[polymorph] host: {topo['arch']} {topo['physical_cores']}p/{topo['logical_cores']}l "
            f"simd={derived['best_simd']} align={derived['alignment_bytes']}B "
            f"gpus={len(topo['gpus'])}"
        )
        print(
            f"[polymorph] rewrote {rewrite['files_rewritten']}/{rewrite['files_processed']} "
            f"file(s) -> {cache_dir}"
        )
    except Exception as exc:  # noqa: BLE001 - polymorphization must not abort the build
        print(f"[polymorph] skipped: {exc}")


def _maybe_hardware_probe(workspace: Path) -> None:
    config = _workspace_json_config(workspace)
    if not config.get("hardware_profiling", {}).get("probe_at_compile_time"):
        return
    from src.hardware_profiling.profiler import HardwareProfiler

    print("\n[hardware] probing host...")
    try:
        profiler = HardwareProfiler(config)
        recipe = profiler.generate_recipe(profiler.probe())
        print(f"[hardware] recipe: parallelism={recipe.get('parallelism')} "
              f"unroll={recipe.get('unroll_factor')} "
              f"vectorization={recipe.get('vectorization_target', 'none')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[hardware] probe skipped: {exc}")


def _maybe_run_evolution(workspace: Path) -> None:
    config_path = workspace / "blueprint_config.json"
    config = _workspace_json_config(workspace)
    if not config.get("project", {}).get("evolutionary_bootstrap", {}).get("enabled"):
        return
    from src.evolution.bootstrap import SelfEvolutionEngine

    print("\n[evolution] running bounded self-evolution pass...")
    try:
        engine = SelfEvolutionEngine(config_path, workspace)
        best = engine.evolve(max_generations=min(3, engine.max_generations))
        print(f"[evolution] best candidate {best.id} fitness={ {k: round(v, 2) for k, v in best.fitness.items()} }")
    except Exception as exc:  # noqa: BLE001
        print(f"[evolution] skipped: {exc}")


def _maybe_submit_hpc_build(context: dict, workspace: Path, args: argparse.Namespace) -> bool:
    """Submit the build as a cluster job when HPC is enabled. Returns True if so."""
    from src.hpc.scheduler import HPCScheduler

    scheduler = HPCScheduler(context)
    if not scheduler.enabled or scheduler.build_on_login_node:
        return False
    if not scheduler.available():
        print(f"[hpc] {scheduler.scheduler} CLI not found; building locally instead.")
        return False

    build_cmd = f"python main.py build --workspace {workspace} --no-hpc --cycles {args.cycles}"
    commands = [build_cmd]
    if scheduler.post_build_run and context.get("runtime", {}).get("benchmark_command"):
        commands.append(context["runtime"]["benchmark_command"])

    job = scheduler.submit(commands, job_name="aero_build", workdir=str(workspace))
    if not job.submitted:
        print(f"[hpc] submission failed ({job.error}); building locally instead.")
        return False
    print(f"[hpc] submitted build job {job.job_id} to {scheduler.scheduler}; waiting...")
    job = scheduler.wait(job)
    print(f"[hpc] build job {job.job_id} finished with state {job.state}")
    return job.succeeded


def _run_runtime_stage(context: dict, workspace: Path) -> None:
    from src.runtime.feedback import RuntimeFeedback

    feedback = RuntimeFeedback(context)
    if not feedback.enabled:
        return
    print("\n[runtime] running benchmark...")
    metrics = feedback.run_benchmark(workdir=str(workspace))
    if metrics.success:
        print(f"[runtime] wall_time={metrics.wall_time:.4f}s "
              f"cpu_time={metrics.cpu_time:.4f}s peak_rss={metrics.peak_rss_mb:.1f}MB")
        if metrics.accuracy_error is not None:
            print(f"[runtime] accuracy_error={metrics.accuracy_error:.3e}")
    else:
        print(f"[runtime] benchmark did not succeed: {metrics.error}")


def _run_validation_stage(context: dict, workspace: Path) -> int:
    from src.validation.validator import Validator

    validator = Validator(context)
    if not validator.enabled:
        return 0
    print("\n[validation] running suite...")
    report = validator.run(workdir=str(workspace))
    for case in report.cases:
        print(f"  [{'PASS' if case.passed else 'FAIL'}] {case.name}")
    print(f"[validation] {report.summary}")
    if not report.passed and validator.is_gatekeeper:
        print("[validation] FAILED (gatekeeper) -> build marked unsuccessful")
        return 1
    return 0


def check_command(args: argparse.Namespace) -> int:
    """Strictly validate a block-format ``blueprint.aero`` without building.

    Prints an ultra-clear ``line:column`` + ``^`` diagnostic on failure and
    exits non-zero, so it can gate a build pipeline.
    """
    import blueprint_lang

    workspace = Path(args.workspace).resolve()
    bp_path = Path(args.blueprint) if args.blueprint else workspace / "blueprint.aero"
    if not bp_path.exists():
        print(f"{bp_path}: blueprint file not found", file=sys.stderr)
        return 1

    source = bp_path.read_text(encoding="utf-8")
    if source.strip() and not blueprint_lang.looks_like_blueprint_dsl(source):
        print(
            f"{bp_path}: legacy INI/JSON blueprint detected; the strict DSL "
            "checker only validates block-format blueprints, so nothing to check."
        )
        return 0

    error = blueprint_lang.check_source(source, filename=str(bp_path))
    if error is None:
        print(f"{bp_path}: OK -- blueprint is valid")
        return 0
    print(error, file=sys.stderr)
    return 1


def evolve_command(args: argparse.Namespace) -> int:
    """Run the self-evolution bootstrap engine."""
    from src.evolution.bootstrap import SelfEvolutionEngine

    config_path = Path(args.config) if args.config else _BLUEPRINT_CONFIG
    workspace = Path(args.workspace).resolve()
    engine = SelfEvolutionEngine(config_path, workspace)
    best = engine.evolve(max_generations=args.generations)
    print(f"\nEvolution complete.  Best candidate: {best.id}")
    print(f"  Fitness: {best.fitness}")
    print(f"  Genome:  {best.genome}")
    return 0


def analyze_command(args: argparse.Namespace) -> int:
    """Run the semantic proximity mapping engine."""
    from src.analysis.semantic_mapper import SemanticMapper

    config = _load_blueprint_config(args.config)
    project_root = Path(args.workspace).resolve()
    mapper = SemanticMapper(config)
    mapper.build_uast(project_root)

    stats = mapper.get_statistics()
    print("\nSemantic Analysis complete.")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if args.export:
        export_path = Path(args.export)
        mapper.export_graph(export_path)
        print(f"  UAST exported to {export_path}")
    return 0


def shield_command(args: argparse.Namespace) -> int:
    """Run the precision shield validator."""
    from src.precision_shield.shield import PrecisionShield

    config = _load_blueprint_config(args.config)
    project_root = Path(args.workspace).resolve()
    shield = PrecisionShield(config)
    results = shield.validate_all(project_root)

    print("\nPrecision Shield Validation:")
    all_passed = True
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.zone_id}")
        for v in result.violations:
            print(f"         - {v}")
        if not result.passed:
            all_passed = False
    return 0 if all_passed else 1


def profile_command(args: argparse.Namespace) -> int:
    """Run the hardware profiling engine."""
    from src.hardware_profiling.profiler import HardwareProfiler

    config = _load_blueprint_config(args.config)
    profiler = HardwareProfiler(config)
    profile = profiler.probe()
    saved = profiler.save_profile(profile)
    recipe = profiler.generate_recipe(profile)

    print(f"\nHardware Profile saved to {saved}")
    print(f"  CPU: {profile.cpu_model}  ({profile.cpu_count} cores)")
    print(f"  Arch: {profile.arch}")
    print(f"  Memory: {profile.total_memory_bytes / 1024**3:.1f} GB")
    print(f"  Cache levels: {len(profile.cache_hierarchy)}")
    print(f"  SIMD sets: {[s.instruction_set for s in profile.simd_capabilities if s.available]}")
    print(f"\nGenerated recipe:")
    for k, v in recipe.items():
        print(f"  {k}: {v}")
    return 0


def cache_command(args: argparse.Namespace) -> int:
    """Show or clear the memoization cache."""
    from src.memoization.cache_engine import MemoizationEngine

    config = _load_blueprint_config(args.config)
    engine = MemoizationEngine(config)

    if args.action == "stats":
        s = engine.stats()
        print("\nMemoization Cache stats:")
        for k, v in s.items():
            print(f"  {k}: {v}")
    elif args.action == "clear":
        engine.cache.clear()
        print("Cache cleared.")
    elif args.action == "cycles":
        cycles = engine.check_dependency_cycles()
        if cycles:
            print(f"Detected {len(cycles)} dependency cycle(s):")
            for c in cycles:
                print(f"  {' -> '.join(c)}")
        else:
            print("No dependency cycles detected.")
    return 0


def libraries_command(args: argparse.Namespace) -> int:
    """Probe numerical libraries (BLAS/LAPACK/MPI/CUDA) and emit linker flags."""
    from src.build.library_tuner import LibraryTuner

    config = _load_blueprint_config(args.config)
    tuner = LibraryTuner(config)
    detected = tuner.detect_all()

    print("\nNumerical Library Detection:")
    for name, lib in detected.items():
        status = "found" if lib.found else "not found"
        extra = f" ({lib.flavor} {lib.version})".rstrip() if lib.found else ""
        print(f"  [{status:9}] {name}{extra}  via {lib.detected_via}")
        if lib.linker_flags:
            print(f"             linker: {' '.join(lib.linker_flags)}")
    print(f"\nAggregate linker flags : {' '.join(tuner.linker_flags(detected)) or '(none)'}")
    print(f"Aggregate compile flags: {' '.join(tuner.compiler_flags(detected)) or '(none)'}")
    space = tuner.genome_space(detected)
    if space:
        print("\nEvolvable library genome space:")
        for gene, values in space.items():
            print(f"  {gene}: {values}")
    return 0


def gpu_command(args: argparse.Namespace) -> int:
    """Plan (and optionally run) GPU kernel compilation."""
    from src.build.gpu_pipeline import GPUPipeline

    config = _load_blueprint_config(args.config)
    project_root = Path(args.workspace).resolve()
    pipeline = GPUPipeline(config)
    plan = pipeline.plan(project_root)

    print("\nGPU Offloading Plan:")
    print(f"  enabled  : {plan['enabled']}")
    print(f"  backend  : {plan['backend']}")
    print(f"  compiler : {plan['compiler']} (available: {plan['available']})")
    print(f"  kernels  : {plan['kernel_count']}")
    for step in plan["compile_steps"]:
        print(f"    - {step['source']} -> {step['output']}")
    print(f"  link flags: {' '.join(plan['link_flags']) or '(none)'}")

    if args.compile:
        results = pipeline.compile_kernels(project_root)
        print("\nCompilation results:")
        for r in results:
            print(f"    [{r.status}] {r.source}")
    return 0


def physics_command(args: argparse.Namespace) -> int:
    """Run heuristic dimensional analysis over the project's Python sources."""
    from src.physics.units import DimensionalAnalyzer

    config = _load_blueprint_config(args.config)
    project_root = Path(args.workspace).resolve()
    analyzer = DimensionalAnalyzer(config)

    if not analyzer.enabled:
        print("\nPhysics symbolic_validation is disabled in the blueprint; nothing to check.")
        return 0

    warnings = analyzer.analyze_project(project_root)
    print(f"\nDimensional Analysis ({len(warnings)} warning(s)):")
    for w in warnings:
        print(f"  {w}")
    return 0 if not warnings else 1


def hpc_command(args: argparse.Namespace) -> int:
    """Generate (and optionally submit) an HPC batch script for the build."""
    import blueprint_parser
    from src.hpc.scheduler import HPCScheduler

    workspace = Path(args.workspace).resolve()
    context = blueprint_parser.parse_blueprint(str(workspace / "blueprint.aero"))
    scheduler = HPCScheduler(context)

    if not scheduler.enabled:
        print("HPC scheduler is 'none'; nothing to submit (builds run locally).")
        return 0

    commands = [args.command_to_run] if args.command_to_run else ["python main.py build --no-hpc"]
    if args.submit:
        if not scheduler.available():
            print(f"{scheduler.submit_binary} not found on PATH; cannot submit.")
            return 1
        job = scheduler.submit(commands, job_name="aero_build", workdir=str(workspace))
        print(f"Submitted: {job.to_dict()}")
        return 0 if job.submitted else 1

    print(scheduler.generate_script(commands, job_name="aero_build", workdir=str(workspace)))
    return 0


def validate_command(args: argparse.Namespace) -> int:
    """Run the validation suite against the built artefacts."""
    from src.validation.validator import Validator

    config = _load_blueprint_config(args.config)
    validator = Validator(config)
    if not validator.enabled:
        print("No validation.execution_command configured.")
        return 0
    report = validator.run(workdir=str(Path(args.workspace).resolve()))
    print("\nValidation Report:")
    for case in report.cases:
        print(f"  [{'PASS' if case.passed else 'FAIL'}] {case.name}")
    print(f"  {report.summary}")
    return 0 if report.passed else 1


def ingest_command(args: argparse.Namespace) -> int:
    """Ingest external source trees declared in the [context] section."""
    from src.context.ingest import ContextIngestor

    config = _load_blueprint_config(args.config)
    workspace = Path(args.workspace).resolve()
    ingestor = ContextIngestor(config, workspace)
    report = ingestor.ingest_all()

    print("\nContext Ingestion:")
    print(f"  sources        : {report['source_count']}")
    print(f"  files ingested : {report['files_ingested']}")
    print(f"  files repaired : {report['files_repaired']}")
    for src in report["sources"]:
        status = src["error"] or f"{src['files_ingested']} file(s) -> {src['target_mapping']}"
        print(f"    - {src['path']}: {status}")
    if report["errors"]:
        print("  errors:")
        for err in report["errors"]:
            print(f"    ! {err}")
    print(f"  report         : {workspace / ContextIngestor.REPORT_NAME}")
    return 0 if not report["errors"] else 1


def invariants_command(args: argparse.Namespace) -> int:
    """Ingest unstructured context + source files into the Invariant Schema.

    Reads every .txt/.md/.pdf/.json/.cpp/.py file under --source-dir, extracts
    state variables, algorithmic boundaries and equations per domain, and
    writes the result (plus the cross-domain system graph) as a JSON
    compilation input for downstream code generator nodes.
    """
    from src.semantic_fluidity import ContextIngestionEngine

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"{source_dir}: directory not found", file=sys.stderr)
        return 1

    workspace = Path(args.workspace).resolve()
    output_path = Path(args.output) if args.output else workspace / ContextIngestionEngine.REPORT_NAME

    engine = ContextIngestionEngine()
    payload = engine.ingest_and_export(source_dir, output_path)
    schema = payload["invariant_schema"]

    print("\nSemantic Fluidity Ingestion:")
    print(f"  domains          : {', '.join(schema['domains']) or '(none)'}")
    print(f"  state variables  : {len(schema['state_variables'])}")
    print(f"  boundaries       : {len(schema['boundaries'])}")
    print(f"  equations        : {len(schema['equations'])}")
    print(f"  system graph     : {payload['graph_statistics']['node_count']} node(s), "
          f"{payload['graph_statistics']['edge_count']} edge(s), "
          f"{payload['graph_statistics']['cross_domain_edges']} cross-domain edge(s)")
    if payload["ingestion_errors"]:
        print("  errors:")
        for err in payload["ingestion_errors"]:
            print(f"    ! {err}")
    print(f"  report           : {output_path}")
    return 0


def infer_command(args: argparse.Namespace) -> int:
    """Infer the full execution DAG from an ultra-lean blueprint.

    Parses the few lines of semantic intent in blueprint.aero, scans the project
    directory, and prints the inferred targets, language/FFI boundaries,
    dependencies and execution order -- the graph that `build` would run with no
    further input.  With --json, emits the machine-readable inferred DAG.
    """
    from src.invisible_config import InvisibleConfigEngine, looks_like_lean_blueprint

    workspace = Path(args.workspace).resolve()
    bp_path = Path(args.blueprint) if args.blueprint else workspace / "blueprint.aero"
    if not bp_path.exists():
        print(f"{bp_path}: blueprint file not found", file=sys.stderr)
        return 1

    content = bp_path.read_text(encoding="utf-8")
    if not looks_like_lean_blueprint(content):
        print(
            f"{bp_path}: not an ultra-lean blueprint; `infer` only applies to the "
            "Invisible Configuration dialect (project \"name\" + ingest/targets/optimize).",
            file=sys.stderr,
        )
        return 1

    engine = InvisibleConfigEngine(bp_path.parent)
    dag = engine.infer_from_source(content)

    if getattr(args, "json", False):
        print(json.dumps(dag.to_dict(), indent=2))
        return 0

    print(f"\nInferred build graph for '{dag.project}' (optimize={dag.optimize}):")
    if dag.has_invariants:
        print(f"  text invariants  : {len(dag.ingest)} ingested source(s) -> {', '.join(dag.ingest)}")
    print("  targets:")
    for target in dag.targets:
        deps = ", ".join(target.depends_on) or "(none)"
        print(f"    - {target.name} [{target.language}/{target.role}] "
              f"{len(target.sources)} source(s); depends on: {deps}")
    print("  ffi / language boundaries:")
    if dag.ffi_boundaries:
        for boundary in dag.ffi_boundaries:
            print(f"    - {boundary.provider} ({boundary.provider_language}) -> "
                  f"{boundary.consumer} ({boundary.consumer_language}) via {boundary.mechanism}")
    else:
        print("    (none)")
    print(f"  execution order  : {' -> '.join(dag.topological_order())}")
    print("  self-healing     : enabled (auto-patches glue-code type mismatches, retries)")
    return 0


def polymorphize_command(args: argparse.Namespace) -> int:
    """Inspect the host and polymorphically rewrite generated code for it.

    Probes CPU vector features, cache topology, core counts and GPUs, then
    rewrites the C/C++/Rust/LLVM-IR files under --source-dir into an ephemeral
    cache (alignment, vectorised micro-kernels, thread-pool sizing) without
    touching the source directory.  With --profile-only it just prints the
    discovered topology.
    """
    from src.polymorphization import PolymorphizationEngine

    engine = PolymorphizationEngine()

    if args.profile_only:
        topology = engine.profile_host()
        derived = topology.to_dict()["derived"]
        print("\nHardware Topology:")
        print(f"  arch             : {topology.arch}")
        print(f"  cores            : {topology.physical_cores} physical / {topology.logical_cores} logical")
        print(f"  cpu features     : {', '.join(topology.cpu_features) or '(none)'}")
        print(f"  best simd        : {derived['best_simd']} ({derived['vector_width_bytes']}B vectors)")
        print(f"  cache line       : {derived['cache_line_bytes']}B  -> alignment {derived['alignment_bytes']}B")
        print(f"  cache levels     : {', '.join('L%d=%dKiB' % (c.level, c.size_bytes // 1024) for c in topology.cache_levels) or '(none)'}")
        print(f"  gpus             : {', '.join('%s/%s' % (g.runtime, g.architecture) for g in topology.gpus) or '(none)'}")
        print(f"  memory           : {topology.total_memory_bytes / 1024**3:.1f} GiB ({topology.memory_bandwidth_class} bandwidth)")
        return 0

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        print(f"{source_dir}: directory not found", file=sys.stderr)
        return 1

    cache_dir = Path(args.cache_dir)
    report = engine.polymerize_tree(source_dir, cache_dir)
    engine.write_report(report, cache_dir)

    topo = report["topology"]
    derived = topo["derived"]
    rewrite = report["rewrite"]
    print("\nAutonomous Hardware-Polymerization:")
    print(f"  host             : {topo['arch']} {topo['physical_cores']}p/{topo['logical_cores']}l")
    print(f"  best simd        : {derived['best_simd']} (align {derived['alignment_bytes']}B, {derived['vector_width_bytes']}B vectors)")
    print(f"  gpus             : {len(topo['gpus'])}")
    print(f"  files processed  : {rewrite['files_processed']}")
    print(f"  files rewritten  : {rewrite['files_rewritten']}")
    print(f"  cache (ephemeral): {cache_dir}")
    return 0


def runtime_command(args: argparse.Namespace) -> int:
    """Run the runtime benchmark and print collected metrics."""
    from src.runtime.feedback import RuntimeFeedback

    config = _load_blueprint_config(args.config)
    feedback = RuntimeFeedback(config)
    if not feedback.enabled:
        print("Runtime feedback is disabled or no benchmark_command configured.")
        return 0
    metrics = feedback.run_benchmark(workdir=str(Path(args.workspace).resolve()))
    print("\nRuntime Metrics:")
    for k, v in metrics.to_dict().items():
        print(f"  {k}: {v}")
    return 0 if metrics.success else 1


# ------------------------------------------------------------------
# Parser
# ------------------------------------------------------------------


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aero Multi-Tool: next-generation build orchestration CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- build (original) ---
    build_parser = subparsers.add_parser("build", help="Run the full builder pipeline")
    build_parser.add_argument("--workspace", default=".", help="Workspace root to build")
    build_parser.add_argument("--cycles", type=int, default=3, help="Number of orchestration cycles")
    build_parser.add_argument(
        "--telemetry-interval",
        type=float,
        default=2.0,
        help="Seconds between telemetry refreshes",
    )
    build_parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    build_parser.add_argument("--no-hpc", action="store_true", help="Force a local build, ignoring [hpc] settings")
    build_parser.add_argument("--no-evolution", action="store_true", help="Skip the self-evolution pass after building")
    build_parser.add_argument("--no-hardware-probe", action="store_true", help="Skip hardware profiling at build start")
    build_parser.add_argument("--no-polymorph", action="store_true", help="Skip autonomous hardware-polymerization of generated code")
    build_parser.add_argument("--runtime-feedback", action="store_true", help="Run the runtime benchmark after building")
    build_parser.add_argument("--validation-only", action="store_true", help="Skip the build; only run the validation suite")
    build_parser.set_defaults(handler=build_command)

    # --- check (strict blueprint validation, no build) ---
    check_parser = subparsers.add_parser(
        "check", help="Strictly validate a block-format blueprint.aero (no build)"
    )
    check_parser.add_argument("--workspace", default=".", help="Workspace root containing blueprint.aero")
    check_parser.add_argument("--blueprint", default=None, help="Explicit path to a blueprint file")
    check_parser.set_defaults(handler=check_command)

    # --- evolve ---
    evolve_parser = subparsers.add_parser("evolve", help="Run the self-evolution bootstrap engine")
    evolve_parser.add_argument("--workspace", default=".", help="Workspace root")
    evolve_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    evolve_parser.add_argument("--generations", type=int, default=10, help="Max generations")
    evolve_parser.set_defaults(handler=evolve_command)

    # --- analyze ---
    analyze_parser = subparsers.add_parser("analyze", help="Run semantic proximity mapping")
    analyze_parser.add_argument("--workspace", default=".", help="Project root")
    analyze_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    analyze_parser.add_argument("--export", default=None, help="Export UAST graph to JSON file")
    analyze_parser.set_defaults(handler=analyze_command)

    # --- shield ---
    shield_parser = subparsers.add_parser("shield", help="Run precision shield validation")
    shield_parser.add_argument("--workspace", default=".", help="Project root")
    shield_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    shield_parser.set_defaults(handler=shield_command)

    # --- profile ---
    profile_parser = subparsers.add_parser("profile", help="Run hardware profiling")
    profile_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    profile_parser.set_defaults(handler=profile_command)

    # --- cache ---
    cache_parser = subparsers.add_parser("cache", help="Manage the memoization cache")
    cache_parser.add_argument("action", choices=["stats", "clear", "cycles"], help="Cache action")
    cache_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    cache_parser.set_defaults(handler=cache_command)

    # --- libraries ---
    lib_parser = subparsers.add_parser("libraries", help="Probe numerical libraries and emit flags")
    lib_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    lib_parser.set_defaults(handler=libraries_command)

    # --- gpu ---
    gpu_parser = subparsers.add_parser("gpu", help="Plan/compile GPU kernels")
    gpu_parser.add_argument("--workspace", default=".", help="Project root")
    gpu_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    gpu_parser.add_argument("--compile", action="store_true", help="Actually compile (needs nvcc/hipcc)")
    gpu_parser.set_defaults(handler=gpu_command)

    # --- physics ---
    physics_parser = subparsers.add_parser("physics", help="Run dimensional-analysis checks")
    physics_parser.add_argument("--workspace", default=".", help="Project root")
    physics_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    physics_parser.set_defaults(handler=physics_command)

    # --- ingest ---
    ingest_parser = subparsers.add_parser("ingest", help="Ingest external source trees ([context])")
    ingest_parser.add_argument("--workspace", default=".", help="Workspace root to ingest into")
    ingest_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    ingest_parser.set_defaults(handler=ingest_command)

    # --- invariants (semantic fluidity) ---
    invariants_parser = subparsers.add_parser(
        "invariants", help="Ingest unstructured context + code into the Invariant Schema"
    )
    invariants_parser.add_argument("--source-dir", required=True, help="Directory of mixed context files to ingest")
    invariants_parser.add_argument("--workspace", default=".", help="Workspace root (used to resolve the default report path)")
    invariants_parser.add_argument("--output", default=None, help="Explicit path for the invariant_schema_report.json")
    invariants_parser.set_defaults(handler=invariants_command)

    # --- infer (invisible configuration layer) ---
    infer_parser = subparsers.add_parser(
        "infer", help="Infer the full execution DAG from an ultra-lean blueprint"
    )
    infer_parser.add_argument("--workspace", default=".", help="Workspace root containing blueprint.aero")
    infer_parser.add_argument("--blueprint", default=None, help="Explicit path to a lean blueprint file")
    infer_parser.add_argument("--json", action="store_true", help="Emit the inferred DAG as JSON")
    infer_parser.set_defaults(handler=infer_command)

    # --- polymorphize (autonomous hardware-polymerization) ---
    poly_parser = subparsers.add_parser(
        "polymorphize", help="Inspect the host and polymorphically rewrite generated code for it"
    )
    poly_parser.add_argument("--source-dir", default="build_artifacts", help="Directory of generated code to rewrite")
    poly_parser.add_argument(
        "--cache-dir", default=str(Path(".aero") / "polymorph_cache"), help="Ephemeral output cache directory"
    )
    poly_parser.add_argument("--profile-only", action="store_true", help="Only print the host topology; do not rewrite")
    poly_parser.set_defaults(handler=polymorphize_command)

    # --- hpc ---
    hpc_parser = subparsers.add_parser("hpc", help="Generate or submit an HPC build job")
    hpc_parser.add_argument("--workspace", default=".", help="Project root (reads blueprint.aero)")
    hpc_parser.add_argument("--submit", action="store_true", help="Submit the job (default: just print the script)")
    hpc_parser.add_argument("--command-to-run", default=None, help="Command the job should execute")
    hpc_parser.set_defaults(handler=hpc_command)

    # --- validate ---
    validate_parser = subparsers.add_parser("validate", help="Run the validation suite")
    validate_parser.add_argument("--workspace", default=".", help="Project root")
    validate_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    validate_parser.set_defaults(handler=validate_command)

    # --- runtime ---
    runtime_parser = subparsers.add_parser("runtime", help="Run the runtime benchmark")
    runtime_parser.add_argument("--workspace", default=".", help="Project root")
    runtime_parser.add_argument("--config", default=None, help="Path to blueprint_config.json")
    runtime_parser.set_defaults(handler=runtime_command)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())