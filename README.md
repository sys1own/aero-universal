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
                    └─────┬─────────────────┬─────────────────────┘
                          │                 │
            ┌─────────────▼─────┐  ┌─────────▼────────────┐
            │  Hardware Profiler │  │  Semantic Fluidity   │
            │  (Real-Time        │  │  (Unstructured       │
            │   Topology Probe)  │  │   Context Ingestion) │
            └─────────────┬─────┘  └─────────┬────────────┘
                          │                   │
                          └─────────┬─────────┘
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │         Polymorphic Rewriter                │
                    │  (Memory mapping & SIMD vector patching)     │
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
                    │  Incremental AST Cache & Unified Artifacts   │
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

---

## 🖥️ CLI Usage

The universal `main.py` entry point handles your entire workflow through highly descriptive subcommands:

| Command | Description |
| --- | --- |
| `build` | Triggers the full pipeline: checks schemas, profiles the hardware, updates source text, and compiles. |
| `check` | Validates your structural block configurations and detects syntax errors. |
| `infer` | Generates a scannable visual chart showing all inferred target configurations and FFI bindings. |
| `invariants` | Tests directory parsing by rendering discovered semantic rules down to an intermediate schema file. |
| `polymorphize` | Runs hardware introspection and outputs your raw system topology parameters. |
| `cache` | Manages your AST database (calculates cache sizes, cleans historical logs, flushes old targets). |

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
