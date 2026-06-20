# Aero Multi‑Tool

**A next‑generation build orchestration engine that self‑evolves, bridges multiple languages, safeguards precision, profiles hardware, and caches semantically — turning compilation into a multi‑objective optimisation problem.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Building on the proven foundation of the Aero Build Engine, the Aero Multi‑Tool introduces five breakthrough capabilities:

- **Self‑Evolution Bootstrap Loop** – The tool optimises its own compilation flags, AST transformations, and runtime behaviour via Pareto‑frontier search, continuously improving its own performance.
- **FFI‑Defying Semantic Proximity Mapping** – Unifies Python and Rust ASTs (via PyO3) into a single semantic graph, enabling dead‑code elimination, data‑flow analysis, and cross‑language inlining across language boundaries.
- **Precision Shield (Immutable Const Zones)** – Protects critical numeric invariants (crypto, ML, financial) from aggressive optimisations using SMT‑based equivalence checking (Z3).
- **Predictive Hardware‑Level Profiling** – Runs lightweight micro‑benchmarks at compile time to characterise cache hierarchies, TLB sizes, and SIMD capabilities, then tunes loop tiling, unrolling, and vectorisation accordingly.
- **Query‑Based Semantic Delta Memoization** – Caches compilation artefacts at the AST‑node level, ignoring whitespace and comment changes; only rebuilds when semantic structure actually changes.

---

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/sys1own/aero-multi-tool.git
cd aero-multi-tool
pip install -r requirements.txt

# Create a minimal blueprint (JSON)
echo '{"project":{"name":"my-simulator"},"graph":{"targets":[{"name":"main","source":"src/main.py","output":"build/main.py"}]},"compiler":{},"cortex":{}}' > blueprint.aero

# Build
python main.py build --workspace .
```

For real‑world examples, see the [examples/](examples/) directory.

---

## Overview

The Aero Multi‑Tool transforms the build process from a linear sequence of commands into an **adaptive, multi‑objective optimisation pipeline**. It:

- Parses a declarative `blueprint.aero` manifest (JSON or INI format).
- Scans your source tree (Python, Rust, and C) to build a unified abstract syntax tree (UAST).
- Profiles the host hardware and selects optimal polyhedral schedules.
- Evolves a population of compiler configurations, each tested in an isolated sandbox.
- Prunes dead code and applies AST‑level transformations, while respecting protected zones.
- Caches all intermediate results at the semantic level.

The result is a build that is **faster, smaller, and more correct** — and that improves over time as the tool learns from its own performance.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │           blueprint.aero (JSON/INI)        │
                    └─────────────────┬───────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────────┐
                    │         Orchestrator (orchestrator.py)      │
                    └─────┬─────────────────┬─────────────────────┘
                          │                 │
            ┌─────────────▼─────┐  ┌─────────▼────────────┐
            │  Hardware Profiler │  │  Semantic Mapper     │
            │  (predictive       │  │  (UAST builder,      │
            │   micro‑benchmarks)│  │   cross‑lang edges)  │
            └─────────────┬─────┘  └─────────┬────────────┘
                          │                   │
                          └─────────┬─────────┘
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │         Self‑Evolution Engine              │
                    │  (NSGA‑II, Pareto frontier, sandboxed)     │
                    └─────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │  Compactor & Translator    │
                    │  (AST pruning, minify,     │
                    │   .aeroc generation)       │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────────────────┐
                    │  Build Artifacts & Cache (query‑based)     │
                    └─────────────────────────────────────────────┘
```

### Core Modules

| Module | Path | Responsibility |
|--------|------|----------------|
| **Blueprint Parser** | `blueprint_parser.py` | Loads and validates the JSON‑ or INI‑based `blueprint.aero`. |
| **Hardware Profiler** | `src/hardware_profiling/profiler.py` | Executes micro‑benchmarks to characterise cache, TLB, SIMD. |
| **Semantic Mapper** | `src/analysis/semantic_mapper.py` | Builds UAST, detects PyO3 FFI edges, runs cross‑language data‑flow analysis. |
| **Self‑Evolution Engine** | `src/evolution/bootstrap.py` | Implements evolutionary loop with Pareto sorting, sandboxing, checkpointing. |
| **Genetic Operators** | `src/evolution/genetic_operators.py` | Mutation and crossover functions for evolutionary search. |
| **Fitness Functions** | `src/evolution/fitness_functions.py` | Evaluation metrics (latency, memory, size, coverage). |
| **Pareto Frontier** | `src/evolution/pareto_frontier.py` | Non‑dominated sorting, crowding distance, hypervolume. |
| **Sandbox Manager** | `src/evolution/sandbox_manager.py` | Isolated process/namespace execution for candidate binaries. |
| **Precision Shield** | `src/precision_shield/shield.py` | SMT‑based equivalence checking; AST‑level protection. |
| **Query Cache** | `src/memoization/cache_engine.py` | Stores AST‑node hashes and compilation results; Salsa‑style incremental recomputation. |
| **Compactor & Translator** | `compactor.py` (root) / `translator/aero_translator.py` | AST dead‑code elimination, minification, serialisation to `.aeroc`. |
| **Orchestrator** | `orchestrator.py` | Coordinates all phases, manages build cycles, renders telemetry. |

> **Note:** The `src/` directory contains the core pluggable components. The root‑level scripts (`orchestrator.py`, `main.py`, etc.) tie everything together.

---

## Installation

### Prerequisites

- **Python 3.11+**
- **Rust** (for native components and PyO3)
- **Z3** (optional, for SMT‑based precision shielding)

### Steps

```bash
git clone https://github.com/sys1own/aero-multi-tool.git
cd aero-multi-tool
pip install -r requirements.txt
```

The `requirements.txt` includes:
- `tree-sitter`, `tree-sitter-rust` – for Rust AST parsing
- `networkx` – for UAST graph manipulation
- `z3-solver` – for SMT invariant validation
- `numpy`, `scipy` – for evolutionary algorithms
- `pytest`, `coverage` – for test suite

Install Rust if not already present:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustup default stable
```

---

## Blueprint Reference

The Aero Multi‑Tool supports **four blueprint formats**: the ultra‑lean **Invisible Configuration Layer** (a few lines of pure intent — everything else inferred), the declarative **block DSL** (strictly validated before the build), modern **JSON**, and legacy **INI** (for backward compatibility).

### Zero‑config (invisible) vs. explicit blueprints

There are two ways to drive Aero, and it's worth being clear about which you're in:

| | **Zero‑config (invisible)** | **Explicit blueprint** |
|---|---|---|
| **What you write** | A few lines of intent: `project`, `ingest`, `targets`, `optimize`. | Full `target` blocks with `language`, `sources`, `requires`, etc. |
| **Who decides the build** | Aero **infers** languages, the DAG, FFI boundaries and error‑correction loops by scanning the project tree. | **You** declare everything; Aero builds exactly what's written. |
| **Format** | The lean dialect (no `[`, `{`, or `"name" {`). | Block DSL, JSON, or INI. |
| **Best for** | Getting started, prototypes, "just build it". | Reproducible builds, subdirectory crates, pinned versions, CI. |
| **See exactly what it did** | `aero infer` (explains every detection). | `aero check` (validates) + `aero build --debug`. |

**Rules of thumb:**

- If `blueprint.aero` contains only `project "name"` plus flat `key = value`
  lines, Aero is in **zero‑config** mode — run `aero infer` to see precisely
  what it detected and why before building.
- The moment you need to **pin a dependency version, point at a subdirectory
  crate, or control RUSTFLAGS**, switch to an **explicit** `target` block (block
  DSL or JSON) — those knobs live on the target.
- Both modes converge on the same internal build graph, so you can start
  zero‑config and graduate to explicit without changing tools.
- When a build fails, run `aero build --debug` to print the synthesised
  manifest, the exact `cargo` command, the injected environment (RUSTFLAGS),
  and the detected dependencies. For Rust "method not found" failures, Aero also
  prints a **root‑cause hypothesis** with the actual dependency version in use.

### Invisible Configuration Layer (ultra-lean)

Shrink the whole blueprint to a few lines of **semantic intent**. The tool infers
the entire execution DAG, per‑target languages, FFI/language boundaries and
self‑healing error‑correction loops from the files in the project directory — so
running `aero` requires **zero further input**. Implemented in
[`src/invisible_config`](src/invisible_config/) (`DAGInferenceEngine` +
`SelfHealingExecutor`, orchestrated by `InvisibleConfigEngine`).

```aero
project "biophysical_trader"

ingest   = ["./research/genomics.md", "./research/market_liquidity.txt"]
targets  = ["cpp_core", "python_dashboard"]
optimize = "maximum_hardware"
```

**What gets inferred** by scanning the project directory:

1. **Languages & sources** — each target name is matched against the file tree;
   `cpp_core` → C++ (`core/*.cpp`), `python_dashboard` → Python (`dashboard/*.py`).
2. **The execution DAG** — compiled "core" targets depend on the **text
   invariants** extracted from the `ingest` files (the same Invariant Schema the
   [Semantic Fluidity engine](#semantic-fluidity-engine) produces); dynamic
   targets depend on the cores they call.
3. **FFI / language boundaries** — C++↔Python via **pybind11**, Rust↔Python via
   **PyO3**, C↔Python via **ctypes** — mapped automatically.
4. **Self‑healing loops** — if a compile step fails on a **type mismatch at a
   boundary**, the `SelfHealingExecutor` patches the glue code (inserts a cast /
   coercion shim) and retries, up to a bounded number of attempts.

The `optimize` intent word (`maximum_hardware` / `balanced` / `size` / `debug`)
maps onto concrete optimizer flags and opt‑in subsystems (hardware
polymorphization, GPU, numerical libraries).

**Inspect the inferred graph (no build):**

```bash
python main.py infer                                        # uses ./blueprint.aero
python main.py infer --blueprint blueprint.aero.lean.sample # a specific file
python main.py infer --json                                 # machine-readable DAG
```

Example output:

```text
Inferred build graph for 'biophysical_trader' (optimize=maximum_hardware):
  text invariants  : 2 ingested source(s) -> ./research/genomics.md, ./research/market_liquidity.txt
  targets:
    - cpp_core [cpp/core] 2 source(s); depends on: text_invariants
    - python_dashboard [python/binding] 1 source(s); depends on: cpp_core
  ffi / language boundaries:
    - cpp_core (cpp) -> python_dashboard (python) via pybind11
  execution order  : cpp_core -> python_dashboard
  self-healing     : enabled (auto-patches glue-code type mismatches, retries)
```

A lean blueprint flows straight through `python main.py build` — the inferred
graph plugs directly into the core execution system. See
[`blueprint.aero.lean.sample`](blueprint.aero.lean.sample).

### JSON Format

The JSON blueprint is a single object with the following **required** top‑level sections:

- `project` – project metadata and self‑evolution settings.
- `graph` – build targets and dependencies.
- `compiler` – AST compaction and optimisation passes.
- `cortex` – multi‑objective evolutionary parameters.

Optional sections enable advanced features:
- `analysis` – semantic proximity mapping configuration.
- `precision_shield` – protected zones and SMT validation.
- `hardware_profiling` – micro‑benchmark parameters.
- `memoization` – query‑based caching settings.
- `context` – context ingestion and code repair.
- `frameworks` – external library integration.
- `runtime` – runtime feedback and benchmarking.
- `validation` – test suite and validation gates.
- `physics` – physics‑specific invariant checks (unit analysis, constants).

### Example `blueprint.aero` (JSON)

```json
{
  "project": {
    "name": "aero-multi-tool",
    "version": "2.0.0",
    "evolutionary_bootstrap": {
      "enabled": true,
      "max_generations": 50,
      "population_size": 16,
      "fitness_objectives": {
        "compilation_latency": { "weight": 0.40 },
        "memory_peak_rss": { "weight": 0.30 },
        "binary_footprint": { "weight": 0.30 }
      },
      "mutation_vectors": {
        "rustc_codegen_flags": ["-C target-cpu=native", "-C opt-level=3"],
        "ast_inlining_aggressiveness": { "range": [0, 100], "step": 10 }
      },
      "validation_suite": {
        "test_command": "cargo test && pytest",
        "required_coverage_minimum": 0.95
      }
    }
  },
  "graph": {
    "targets": [
      {"name": "core", "source": "src/core.py", "output": "build/core.py"}
    ],
    "dependencies": {"core": []},
    "workspace_mode": "incremental",
    "allow_partial_graph": false
  },
  "compiler": {
    "optimization_level": "O3",
    "dead_code_elimination_passes": 6
  },
  "cortex": {
    "target_accuracy_floor": 0.995,
    "max_processing_latency_limit_us": 20000
  }
}
```

### Block DSL Format (recommended)

A small, declarative, block‑structured language for describing a multi‑language
build. It is handled by the dedicated [`blueprint_lang`](blueprint_lang/) package
(lexer → parser → validator) and is **strictly checked before any build step**:
a single syntax or validation error aborts the run with an exact `line:column`
and a `^` pointer at the problem.

```aero
project "my_universal_app" {
    version = "1.0.0"
}

target "core_engine" {
    language = "cpp"
    sources  = ["src/core/**/*.cpp", "src/core/**/*.hpp"]
    flags    = ["-O3", "-std=c++20"]
}

target "bindings" {
    language = "python"
    requires = ["core_engine"]
    sources  = ["src/bindings/*.py"]
}
```

**Grammar.** A document is a flat list of blocks; each block is
`<type> "<name>" { key = value … }`. Values are quoted strings, numbers,
`true`/`false`, or `[lists]`. Comments start with `#` or `//`.

**Validation rules.** Exactly one `project` block; at least one `target`; only
known keys per block (`target`: `language`, `sources`, `requires`, `flags`,
`defines`, `output`, `optional`, and the Rust/Cargo keys `manifest_path`,
`root`, `cargo_dependencies`, `optimization`, `rustflags`); required keys present (`project.version`,
`target.language`, `target.sources`); `language` ∈ `{c, cpp, fortran, python,
rust}`; unique target names; every `requires` entry must reference a real
target; and the `requires` graph must be **acyclic**.

**Validate it without building** (a clean pre‑flight gate, exit code `0`/`1`):

```bash
python main.py check                       # validates ./blueprint.aero
python main.py check --blueprint app.aero  # validate a specific file
python -m blueprint_lang blueprint.aero    # same check, standalone
```

Example diagnostic for a broken blueprint:

```text
error: unterminated string literal
  --> blueprint.aero:7:15
   |
 7 |     version = "1.0.0
   |               ^ this string is never closed
   |
   = help: strings cannot span lines; add a closing double quote (")
```

See [`blueprint.aero.sample`](blueprint.aero.sample) for a complete example.

### Rust / Cargo support

Aero respects user‑provided Cargo manifests and supports crates that live in
subdirectories. The behaviour for a `language = "rust"` target is:

1. **An existing `Cargo.toml` is used verbatim.** If the crate root already has a
   `Cargo.toml` — discovered from the target's `sources`, or pointed at via
   `manifest_path` / `root` — Aero builds against it **as‑is** and never
   synthesises or overwrites it. Builds that pin older dependency APIs keep
   working.
2. **Otherwise a manifest is synthesised**, and you can pin dependency versions
   from the blueprint (see `cargo_dependencies` / the JSON `cargo` block below).
3. **`cargo` runs from the resolved crate root**, and artefacts are collected
   from *that* crate's `target/` directory.

**New target fields:**

| Field | Format | Meaning |
|-------|--------|---------|
| `root` | string | Subdirectory that is the crate root (e.g. `"crates/foo"`). |
| `manifest_path` | string | Explicit path to a `Cargo.toml` (or the directory containing it). Its directory becomes the crate root. |
| `cargo_dependencies` | list of `"name=version"` | Pin dependency versions for a **synthesised** manifest (block‑DSL / INI form). |

**Block DSL — a crate in a subdirectory with its own committed manifest:**

```aero
target "engine" {
    language = "rust"
    sources  = ["crates/engine/src/lib.rs"]
    root     = "crates/engine"          # cargo runs here; its Cargo.toml is honoured
}
```

**Block DSL — no manifest yet, pin versions for the synthesised one:**

```aero
target "math" {
    language           = "rust"
    sources            = ["src/lib.rs"]
    cargo_dependencies = ["rug=0.22", "serde=1.0"]
}
```

**Richer nested `cargo` block (target metadata).** The Rust backend also accepts
a nested `cargo` object on a target's metadata, supporting inline‑table specs
(features), an explicit `edition`, and `crate_type`. This is the form consumed
by the compiler backend (`src/build/compilers.py`) and is convenient for JSON
target metadata or programmatic callers of `compile_target(...)`:

```json
{
  "name": "engine",
  "language": "rust",
  "sources": ["crates/engine/src/lib.rs"],
  "root": "crates/engine",
  "cargo": {
    "edition": "2021",
    "dependencies": {
      "rug": "0.22",
      "serde": { "version": "1.0", "features": ["derive"] }
    }
  }
}
```

Both forms feed the same place: `cargo.dependencies` (nested) and
`cargo_dependencies` (flat `"name=version"` list) are merged into the
synthesised manifest's `[dependencies]`. Neither is consulted when a
`Cargo.toml` already exists — that manifest always wins.

> Precedence for the crate root: `manifest_path` → `root` → an existing
> `Cargo.toml` found above the sources → the source directory (its parent if the
> sources sit in `src/`) → the workspace root. A synthesised manifest carries a
> header noting that committing your own `Cargo.toml` gives you full control.

#### Controlling RUSTFLAGS (portable by default)

Aero injects `RUSTFLAGS` for Rust targets, but **defaults to injecting nothing**
so builds stay portable across CPUs, CI fleets and cross‑compiles. You opt into
tuning, or take full control, per target:

| Setting | Effect |
|---------|--------|
| *(unset)* | No `RUSTFLAGS` injected — portable. |
| `optimization = "none"` | Explicitly inject nothing (and pass any host `RUSTFLAGS` through). |
| `optimization = "generic"` | `-C target-cpu=generic` (portable, still tuned). |
| `optimization = "native"` | `-C target-cpu=native` (fastest on *this* host; not portable). |
| `optimization = "size"` | `-C opt-level=z`. |
| `rustflags = ["-C", "target-cpu=generic"]` | Used **verbatim**, overriding `optimization`. |

In zero‑config mode the top‑level `optimize` word feeds this too
(`optimize = "maximum_hardware"` ⇒ `target-cpu=native`). If a host rejects the
injected flags (e.g. an unknown `target-cpu`), set `optimization = "none"` or a
`generic` profile.

```aero
target "engine" {
    language     = "rust"
    sources      = ["crates/engine/src/lib.rs"]
    root         = "crates/engine"
    optimization = "none"                       # or: rustflags = ["-C", "target-cpu=generic"]
}
```

#### Debugging a build

`aero build --debug` prints, per target, exactly what Aero used — so version
mismatches and RUSTFLAGS surprises are diagnosable at a glance:

```text
[Debug] engine: cargo command: cargo build --manifest-path crates/engine/Cargo.toml
[Debug] engine: env: RUSTFLAGS=-C target-cpu=generic
[Debug] engine: crate root: .../crates/engine (manifest: existing)
[Debug] engine: dependencies: rug=0.22
[Debug] engine: Cargo.toml in use
        [package] …
```

When a Rust build fails with a *method‑not‑found* error (a classic
version‑mismatch symptom), Aero appends a root‑cause hypothesis naming the
**actual version in use**:

```text
Aero Build Failure
  error[E0599]: no method named `neg_mut` found for struct `rug::Integer` …

  Possible cause (Aero analysis):
    → method `neg_mut` not found on type `rug::Integer`
    → likely cause: a version mismatch — `neg_mut` is not part of the API of `rug::Integer` …
    → crate `rug` in use: 1.24.0 (resolved) — declared as "0.22"
    → check whether `neg_mut` exists in that version of `rug`; if not, pin a compatible
      version, e.g. cargo_dependencies = ["rug=<version>"], then rebuild.
```

### INI Format (Legacy)

For legacy projects, the INI format is still supported. See the original [README](README_legacy.md) for details.

---

## CLI Usage

The `main.py` script provides several subcommands:

| Command | Description |
|---------|-------------|
| `build` | Full build pipeline (scanner → decision tree → tuner → compiler) |
| `check` | Strictly validate a block‑DSL `blueprint.aero` (no build) |
| `infer` | Infer the full execution DAG from an ultra‑lean blueprint (see [Invisible Configuration Layer](#invisible-configuration-layer-ultra-lean)) |
| `ingest` | Ingest external source trees, repair code, and integrate into the workspace |
| `evolve` | Run only the evolutionary optimisation loop (without full build) |
| `analyze` | Perform semantic analysis and generate UAST graph |
| `shield` | Validate precision shields against invariants |
| `profile` | Run hardware profiling and output results |
| `cache` | Manage query cache (list, clear, prune) |
| `libraries` | Auto‑detect and link external libraries (BLAS, LAPACK, etc.) |
| `gpu` | Compile GPU kernels (CUDA/HIP) |
| `physics` | Run physics‑specific invariant checks (units, constants) |
| `hpc` | Submit build to HPC cluster (SLURM/PBS) |
| `validate` | Run the validation suite and report results |
| `runtime` | Execute runtime benchmarks and feed back into fitness |
| `invariants` | Ingest unstructured context + code into the domain‑agnostic Invariant Schema |
| `polymorphize` | Inspect the host and polymorphically rewrite generated code for it (see [Autonomous Hardware-Polymerization](#autonomous-hardware-polymerization)) |

### Common Options

- `--workspace <path>` – root directory containing `blueprint.aero` (default: `.`)
- `--config <path>` – explicit path to blueprint file (JSON or INI)
- `--verbose` – enable debug logging
- `--cycles <n>` – number of build cycles (for iterative improvement)

---

## Semantic Fluidity Engine

Aero can ingest **entirely unstructured context** — medical papers, math
write‑ups, economics prose, JSON config, raw `.cpp`/`.py` source, even
`.pdf` reports — and turn it into a structured **Invariant Schema** that the
code generator nodes can consume as a high‑level compilation input. This is
handled by the [`src/semantic_fluidity`](src/semantic_fluidity/) package via
`ContextIngestionEngine`.

```python
from pathlib import Path
from src.semantic_fluidity import ContextIngestionEngine

engine = ContextIngestionEngine()
schema = engine.ingest_directory(Path("context_sources/"))
compilation_inputs = engine.to_compilation_inputs(schema)
```

**Supported inputs:** `.txt` / `.md`, `.pdf` (dependency‑free fallback parser,
or `pypdf`/`PyPDF2` if installed), `.json`, and source code (`.py`/`.pyi`,
`.cpp`/`.cc`/`.cxx`/`.hpp`/`.hh`, `.c`/`.h`).

**Extraction.** Every file is routed to an extractor based on its format:

| Format | Extractor | Technique |
|--------|-----------|-----------|
| Prose (`.txt`/`.md`/`.pdf`) | `TextRuleExtractor` | Cue‑phrase + regex ("let X be…", "where X denotes…", "X must not exceed N…", `lhs = rhs` equations) |
| Python | `CodeRuleExtractor` | `ast`‑based: module constants, `assert` conditions, single‑expression functions |
| C/C++ | `CodeRuleExtractor` | Regex: `#define`, `const TYPE NAME = VALUE;`, `assert(...)` |
| JSON | `JsonRuleExtractor` | Structured passthrough (`state_variables`/`boundaries`/`equations` keys) or generic scalar flattening |

An `LLMClient` interface (`NullLLMClient` by default) lets a real API or
local model be wired into `LLMAssistedExtractor` for higher‑fidelity
extraction; every extractor above remains fully functional offline.

**The Invariant Schema** namespaces every extracted fact under
`"<domain>::<symbol>"` so unrelated fields never collide — a `rate` found in
a genomics paper and a `rate` found in a game‑engine source file become
`genomics::rate` and `game_engine::rate`, two independent entries:

```json
{
  "domains": ["genomics", "game_engine"],
  "state_variables": [
    {"id": "genomics::rate", "kind": "state_variable", "domain": "genomics", "symbol": "rate", "description": "the mutation rate"},
    {"id": "game_engine::rate", "kind": "state_variable", "domain": "game_engine", "symbol": "rate", "description": "the frame render rate"}
  ],
  "boundaries": [],
  "equations": []
}
```

These never merge, but they **are** connected: `SystemGraph` builds a
`networkx` graph with `defines` edges (domain → invariant), `references`
edges (boundary/equation → same‑domain variable), and `shared_symbol` edges
auto‑detected across domains that share a bare symbol name (like `rate`
above) — so the synthesis layer can reason about both without conflating
them. Explicit cross‑domain relationships can also be declared with
`graph.link_domains(...)`.

**Run it standalone:**

```bash
python main.py invariants --source-dir context_sources/
```

**Or opt it into the build pipeline** via `blueprint_config.json`:

```json
{
  "semantic_fluidity": {
    "enabled": true,
    "source_dir": "context_sources"
  }
}
```

When enabled, `build` ingests `source_dir` and writes
`invariant_schema_report.json` to the workspace before the build proceeds.

---

## Autonomous Hardware-Polymerization

Aero inspects the host machine **at build time** and polymorphically rewrites
the freshly generated C/C++/Rust source (or LLVM IR) to fit that exact
machine — **before the compiler is invoked and with no flags from the user**.
This is handled by the [`src/polymorphization`](src/polymorphization/) package
(`HardwareProfiler` + `PolymorphicRewriter`, orchestrated by
`PolymorphizationEngine`) and runs automatically as a build stage after code
generation but before linking/execution.

**1. `HardwareProfiler` — runtime topology probe (dependency-free).** Reads
`/proc` + `sysfs` (and shells out only to tools already present, e.g.
`nvidia-smi`/`vulkaninfo`), degrading to sane defaults when a source is
unavailable. It discovers:

- CPU vector features — AVX2, AVX-512, SSE, ARM NEON;
- the **physical vs. logical** core split (for thread-pool sizing);
- the L1/L2/L3 cache hierarchy and line sizes;
- available GPU architectures (CUDA `sm_*`, then Vulkan/WebGPU);
- total memory and a coarse memory-bandwidth class.

> Note: this is distinct from the benchmark-driven
> `src/hardware_profiling/profiler.py` (the `profile` command), which *times*
> micro-benchmarks. The polymorphization profiler is purely introspective so it
> is safe to run on every build.

**2. `PolymorphicRewriter` — the rewrite pass.** Generated code uses neutral
placeholders that the rewriter binds to the discovered host:

| Placeholder | Rewritten to | Purpose |
|-------------|--------------|---------|
| `AERO_ALIGN` | e.g. `64` | Memory alignment = max(cache line, vector width) |
| `AERO_WORKERS` | physical core count | Thread-pool worker count (ignores SMT siblings) |
| `AERO_VECTOR_WIDTH` / `AERO_SIMD_LANES_F32` | e.g. `32` / `8` | Vector register width / lane counts |
| `AERO_KERNEL(name)` | `name__avx512` / `name__avx2` / `name__neon` / `name__scalar` | Binds a baseline loop to the best target-specific micro-kernel |
| `AERO_PRAGMA_SIMD` (marker line) | `#pragma omp simd simdlen(N)` (C/C++), `#[target_feature(enable = "avx2")]` (Rust), vectorize hint (LLVM IR) | Language-appropriate vectorization directive |

**3. Transparent & non-destructive.** Rewriting happens entirely in memory
(`engine.polymerize_text(...)`) or into an **ephemeral build cache**
(`.aero/polymorph_cache/`, reset on each run) that mirrors the generated
layout. The user's primary source directory is **never modified** — the
downstream linker compiles the cache.

**Run it standalone:**

```bash
python main.py polymorphize --profile-only                 # just print the host topology
python main.py polymorphize --source-dir build_artifacts/  # rewrite into .aero/polymorph_cache
```

It runs automatically during `build`; opt out with `build --no-polymorph` or:

```json
{
  "polymorphization": {
    "enabled": false,
    "source_dir": "build_artifacts",
    "cache_dir": ".aero/polymorph_cache"
  }
}
```

```python
from src.polymorphization import PolymorphizationEngine

engine = PolymorphizationEngine()
report = engine.polymerize_tree("build_artifacts/", ".aero/polymorph_cache")
# report["topology"] describes the host; report["rewrite"] lists every edit.
```

---

## Output Artifacts

After a successful build, you will find:

| Artifact | Location | Description |
|----------|----------|-------------|
| Optimised sources | `build_artifacts/*.optimized.py` / `.rs` | Dead‑code‑eliminated, optionally minified. |
| UAST graph | `.aero/uast_graph.json` | Serialised cross‑language semantic graph. |
| Hardware profile | `.aero/hardware_profile.json` | Measured cache and SIMD parameters. |
| Evolution checkpoints | `.aero/evolution_checkpoints/` | Population snapshots for each generation. |
| Query cache | `.aero/query_cache/` | AST‑node‑level cached compilation units. |
| Invariant Schema report | `invariant_schema_report.json` | Domain‑namespaced state variables/boundaries/equations + system graph (opt‑in, see [Semantic Fluidity Engine](#semantic-fluidity-engine)). |
| Polymorphization cache | `.aero/polymorph_cache/` | Host‑specialised rewrites of the generated code + `hardware_topology.json` / `polymorphization_report.json` (ephemeral; see [Autonomous Hardware-Polymerization](#autonomous-hardware-polymerization)). |
| Build manifest | `build_manifest.json` | Final configuration and performance metrics. |
| Audit log | `WORKSPACE_AUDIT.md` | Human‑readable summary of the build. |

---

## Telemetry Dashboard

During execution, a live dashboard displays key metrics:

```
==============================================================================
 AERO MULTI‑TOOL ORCHESTRATION TELEMETRY
==============================================================================
 cycle 1/3 | elapsed 4.2s | population 16 | generation 5/50
------------------------------------------------------------------------------
 stages
  - hardware_profiler    ok         0.8s
  - semantic_mapper      ok         2.1s
  - evolution_engine     in_progress
  - compactor            pending
------------------------------------------------------------------------------
 best fitness (latency=0.42, memory=0.55, size=0.38)
 current dominant individual: gen5_0012
 sandbox tests: 42 passed, 0 failed
------------------------------------------------------------------------------
 Pareto front size: 7
 hypervolume indicator: 0.873
==============================================================================
```

---

## Extending the Tool

### Adding a New Language Parser

To support another language (e.g., C++), implement a parser that produces `UnifiedASTNode` objects and add it to the `SemanticMapper` class. Register the language in `analysis.semantic_proximity_mapping.source_roots`.

### Adding a Custom Mutation Vector

Edit the `mutation_vectors` section in `blueprint.aero`. The evolutionary engine will automatically handle new numeric or categorical parameters.

### Integrating a New SMT Solver

Replace the `z3` import in `src/precision_shield/shield.py` with another solver (e.g., `cvc5`), ensuring the same interface for equivalence checking.

### Adding HPC Integration

Implement a new scheduler in `src/hpc/scheduler.py` and register it in the `hpc` subcommand.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `Z3 not installed` | SMT validation required but Z3 missing. | `pip install z3-solver` or disable precision shielding. |
| `tree-sitter-rust not found` | Rust parser dependency missing. | `pip install tree-sitter-rust` or rebuild the grammar. |
| `Sandbox creation failed` | System lacks `unshare` or `cgroups`. | Run without sandboxing (set `sandboxing: "none"` in blueprint). |
| `Evolution stuck at generation 0` | No valid individuals produced. | Check test suite; ensure `validation_suite.test_command` works. |
| `Query cache grows too large` | Cache size exceeds limit. | Increase `max_cache_size_gb` or manually clear `.aero/query_cache`. |

---

## Testing

Run the full test suite:

```bash
pytest tests/ -v --cov=src --cov-report=term
```

Individual tests (e.g., blueprint parsing):

```bash
python -m unittest test_blueprint_parser -v
```

---

## Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository.
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`).
3. **Make your changes** – ensure code quality (PEP 8 for Python, `rustfmt` for Rust).
4. **Add or update tests** for new functionality.
5. **Run the test suite** and a full build to verify.
6. **Commit** (`git commit -m 'Add amazing feature'`).
7. **Push** to your branch (`git push origin feature/amazing-feature`).
8. **Open a pull request** against the `main` branch.

### Coding Guidelines

- Python: follow [PEP 8](https://peps.python.org/pep-0008/) and use `black` for formatting.
- Rust: use `rustfmt` and `clippy`.
- Document new features in the README and in code comments.
- For major new features, update the blueprint schema and provide examples.

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## Acknowledgements

- Built on the original Aero Build Engine.
- Inspired by academic works on superoptimisation (LLVM Souper), polyhedral scheduling (Polly), and SMT‑based verification (Z3).

---

**Happy building!** 🚀
