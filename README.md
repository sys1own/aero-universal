# Aero Universal

**A lean, universal, user-friendly multi-language build engine driven by autonomous semantic synthesis and bare-metal orchestration.**

Aero Universal strips away the complex, hyper-specialized configuration overhead of traditional multi-language build systems. Built upon a high-performance microkernel architecture, it functions as an intuitive, zero-config, domain-agnostic toolchain that translates pure semantic intent into highly optimized native targets.

---

## 🚀 Key Breakthrough Capabilities

* **The "Invisible" Configuration Layer** – Reduces configuration files down to less than ten lines of pure declarative intent. The engine automatically infers execution DAGs, dependency trees, FFI language boundaries, and self-healing compilation loops directly from project contexts.
* **Domain-Agnostic Semantic Fluidity** – Ingests entirely unstructured textual data (e.g., medical research papers, economic textbooks, raw mathematical specifications) alongside multi-language code. It extracts invariant logical rules across wildly differing domains and synthesizes them into a unified software target.
* **Autonomous Hardware-Polymerization** – Performs real-time host architecture introspection. It automatically discovers cache hierarchies, physical core configurations, and SIMD instruction sets (AVX-512, ARM NEON), then polymorphically rewrites memory alignment and code loops for maximum performance—requiring zero compiler optimization flags from the user.
* **AST-Level Delta Memoization** – Caches build artifacts using an incremental structural query system. It tracks abstract syntax tree modifications instead of file hashes, ensuring that changes to whitespace, formatting, or comments never trigger a slow rebuild.

---

## ⚡ Quick Start

```bash
# Clone and enter the repository
git clone https://github.com/sys1own/aero-universal.git
cd aero-universal
pip install -r requirements.txt

# Run the automatic project inference (checks your local workspace and builds automatically)
python main.py build

```

---

## 🏗️ Architecture

Aero Universal utilizes a lightweight **microkernel core** that manages graph scheduling, data dependencies, and process dispatching, while routing language compilation through decoupled, independent toolchain plugins.

```
                    ┌─────────────────────────────────────────────┐
                    │          blueprint.aero (Lean Block/DSL)    │
                    └─────────────────┬───────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────────┐
                    │     DAG Inference Engine (orchestrator.py)  │
                    └─────┬──────────────────┬────────────────────┘
                          │                  │
            ┌─────────────▼─────┐  ┌─────────▼────────────┐
            │ Hardware Profiler │  │  Semantic Fluidity   │
            │ (Real-Time        │  │  (Unstructured       │
            │  Topology Probe)  │  │   Context Ingestion) │
            └─────────────┬─────┘  └──────────┬───────────┘
                          │                   │
                          └─────────┬─────────┘
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │         Polymorphic Rewriter                │
                    │  (Memory mapping & SIMD vector patching)    │
                    └─────────────┬───────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────────────────┐
                    │      Pluggable Microkernel Compilation      │
                    │       (C++ / Rust / Python / Node)          │
                    └─────────────┬───────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────────────────┐
                    │  Incremental AST Cache & Unified Artifacts  │
                    └─────────────────────────────────────────────┘

```

### Core Modules

| Module | Path | Responsibility |
| --- | --- | --- |
| **Blueprint Parser** | `blueprint_lang/` | Lexes, parses, and strictly validates structural block configurations before execution. |
| **DAG Inference Engine** | `src/invisible_config/` | Scans directories to resolve language targets, map FFI layers, and infer dependencies. |
| **Context Ingestion Engine** | `src/semantic_fluidity/` | Parses prose (`.md`, `.txt`, `.pdf`) and extracts namespaced domain invariants. |
| **Hardware Profiler** | `src/polymorphization/profiler.py` | Probes physical hardware architecture (caches, cores, vectors) dynamically. |
| **Polymorphic Rewriter** | `src/polymorphization/rewriter.py` | Modifies source templates to align memory and hook targeted micro-kernels in memory. |
| **Incremental Cache** | `src/memoization/cache_engine.py` | Manages node-level structural memoization using query-based caching. |
| **Unified Orchestrator** | `orchestrator.py` | Controls build phases, handles multi-language error interception, and prints clean UI updates. |

---

## 🛠️ Blueprint Reference

Aero Universal supports two human-friendly configuration modes designed to keep your project setup clean and readable.

### 1. The Invisible Configuration Layer (Under 10 Lines)

This layout completely bypasses explicit file lists. You provide the high-level input locations and target intents, and the `DAGInferenceEngine` takes care of mapping sources, detecting languages, establishing FFI linkages, and activating self-healing repair loops.

```aero
project "biophysical_trader"

ingest   = ["./research/genomics.md", "./research/market_liquidity.txt"]
targets  = ["cpp_core", "python_dashboard"]
optimize = "maximum_hardware"

```

To view what the system infers based on your file tree without running a compilation pass, use the diagnostics tool:

```bash
python main.py infer

```

### 2. Standard Block DSL Format

For explicit structures, use our clean, declarative block language. It validates formatting, checks for cyclic dependencies, and highlights typos instantly before any compilation steps take place.

```aero
project "my_universal_app" {
    version = "1.0.0"
}

target "core_engine" {
    language = "cpp"
    sources  = ["src/core/**/*.cpp", "src/core/**/*.hpp"]
    flags    = ["-std=c++20"]
}

target "bindings" {
    language = "python"
    requires = ["core_engine"]
    sources  = ["src/bindings/*.py"]
}

```

Validate your setup syntax directly via the CLI:

```bash
python main.py check --blueprint blueprint.aero

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

## Standalone Repository Generator

`aero scaffold` turns a **single source file living anywhere on disk** into a
complete, turn‑key, idiomatic Rust/pyo3 project — generated **outside** the tool
tree so `aero-universal` stays pristine. It's the zero‑config path for "I have a
`lib.rs`, give me a repo I can push to GitHub." Implemented in
[`src/scaffold`](src/scaffold/).

```bash
# From a file anywhere — no need to move it into the tool directory
aero scaffold --source-entry /content/lib.rs --distribution-directory ~/out/anyon --verbose

# Or into a throwaway temp dir, and compile it too (with auto-recovery)
aero scaffold --source-entry ../data/core.rs --build
```

**1. Flexible context paths (zero file relocation).** `--source-entry` resolves
absolute paths (`/content/lib.rs`), relative paths (`../data/core.rs`, `~/x.rs`)
and plain workspace‑relative paths. The file is **read from its exact location**
and copied into the transient workspace — it is never moved and the engine never
raises "source not found" for a file that plainly exists. The `[context]`
ingestion path gained the same single‑file‑from‑anywhere support.

**2. Out‑of‑tree workspace isolation.** Every manifest, directory layout,
build‑cache stream and `target/` output goes to a **system temp dir**
(auto‑cleaned) or to your `--distribution-directory` (kept — it's the
deliverable). A guard *refuses* to materialise a workspace inside the tool tree,
so a mis‑configured path can never clutter `aero-universal` again.

**3. Complete standalone repository.** The generated folder is turn‑key:

| File | Contents |
|------|----------|
| `Cargo.toml` | Inferred metadata + dependencies (`rug`, `pyo3`), `crate-type = ["cdylib"]` for a Python extension module. |
| `src/lib.rs` | The corrected, **shielded** source. |
| `.gitignore` | Ignores `target/`, `*.so`, `__pycache__`, … |
| `README.md` | Build + use + verify instructions. |
| `test_binding.py` | A quick Python import/verification check‑script. |

```text
~/out/anyon/
├── Cargo.toml          # [lib] crate-type = ["cdylib"]; rug + pyo3 (extension-module)
├── src/lib.rs          # shielded source
├── .gitignore
├── README.md
└── test_binding.py
# push it: cd ~/out/anyon && git init && git add . && git commit -m 'init'
```

**4. Semantic shields & auto‑error correction.** When the source contains `rug`
or `pyo3` anchors, Aero applies the API fixes codified from live compile testing
**during scaffolding**, idempotently:

- **Hygienic extension‑trait injection** — `neg_mut` / `nth_root` compatibility
  `impl`s are prepended *after* crate‑level inner attributes (`#![...]`, `//!`)
  so they never collide with downstream `use` imports.
- **Type‑cascading alignment** — `let q_dim = match sec { … }` index tables are
  annotated `let q_dim: usize = match sec { … }` (only when the arms are
  integer‑like), stopping a single inferred `i32` cascading downstream.
- **Robust diagnostic recovery** — with `--build`, `cargo build` runs from the
  generated repo; if it exits `101` on a mutability or type‑mismatch error, the
  failing `src/lib.rs` is piped through the auto‑correction pass (e.g. `let x` →
  `let mut x`) and the build is **re‑dispatched once**:

```text
[scaffold] build: attempt 1 failed (code 101); corrections: mut(acc)
[scaffold] build: attempt 2 ok
[scaffold] build: recovered after auto-correction
```

The subsystem is fully modular — `source_resolver`, `rust_shield`, `workspace`,
`repo_generator`, `recovery` and the orchestrating `engine` are independently
usable and tested.

### INI Format (Legacy)

For legacy projects, the INI format is still supported. See the original [README](README_legacy.md) for details.

---

## 🖥️ CLI Usage

The universal `main.py` entry point handles your entire workflow through highly descriptive subcommands:

| Command | Description |
|---------|-------------|
| `build` | Full build pipeline (scanner → decision tree → tuner → compiler) |
| `check` | Strictly validate a block‑DSL `blueprint.aero` (no build) |
| `infer` | Infer the full execution DAG from an ultra‑lean blueprint (see [Invisible Configuration Layer](#1-the-invisible-configuration-layer-under-10-lines)) |
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
| `scaffold` | Generate a turn‑key standalone repo from a source file, out‑of‑tree (see [Standalone Repository Generator](#standalone-repository-generator)) |

### Common Options

- `--workspace <path>` – root directory containing `blueprint.aero` (default: `.`)
- `--config <path>` – explicit path to blueprint file (JSON or INI)
- `--verbose` – enable debug logging
- `--cycles <n>` – number of build cycles (for iterative improvement)

---

## 🌌 Advanced Architectural Subsystems

### Semantic Fluidity Engine

The engine breaks down complex documents by routing files to dedicated structural parsers:

* **Prose (`.txt`, `.md`, `.pdf`):** Isolates relational logic, definitions, and mathematical assignments using a highly robust keyword extraction array.
* **Code Elements (`.py`, `.cpp`, `.rs`):** Tracks function bounds, core constants, assertions, and language boundaries.

To avoid naming conflicts when mixing completely separate domains (like genomics and high-frequency trading), every data attribute is encapsulated within a custom namespace (e.g., `genomics::rate` vs `market::rate`) while plotting shared system variables inside an integrated mapping graph.

### Autonomous Hardware-Polymerization

The compiler bypasses rigid environment properties by swapping generalized source placeholders right before triggering target toolchains:

* `AERO_ALIGN` is mapped directly to the computer's native L1/L2 cache lines to prevent cache thrashing.
* `AERO_WORKERS` mirrors exact physical hardware processors, ignoring hyperthreaded cores to prevent execution overhead.
* `AERO_PRAGMA_SIMD` auto-injects optimization lines calibrated to your machine's unique SIMD registry registers.

---

## 📋 Telemetry & Error Handling

Aero Universal intercepts confusing compiler dumps and presents clean, scannable terminal reporting.

```
==============================================================================
 AERO UNIVERSAL GRAPH TELEMETRY
==============================================================================
 project: biophysical_trader | mode: maximum_hardware | elapsed: 1.4s
------------------------------------------------------------------------------
 execution pipeline
  - context_ingestion     [ OK ] -> 2 domains mapped (genomics, market)
  - hardware_profiler     [ OK ] -> detected avx512, 8 physical cores
  - code_polymerization   [ OK ] -> rewritten alignment lines (64 bytes)
  - target_compilation    [ IN_PROGRESS ] -> compiling cpp_core...
------------------------------------------------------------------------------
 cache status: 84% semantic hits (skipped 12 files)
 self-healing engine: active (0 corrections required)
==============================================================================

```

If a downstream build engine fails due to a syntax problem, type error, or mismatched FFI boundary, Aero catches the stream, parses out the exact error location, and clearly flags it to prevent raw stack trace dumps.

---

## 🧪 Testing

Verify build workflows and parsing logic across our entire test framework:

```bash
pytest tests/ -v

```

---

## 📄 License

Distributed under the MIT License. See [LICENSE](https://www.google.com/search?q=LICENSE) for more details.
