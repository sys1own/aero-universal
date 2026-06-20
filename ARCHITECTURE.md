# Architectural Changes: Physics‑Scale Build Support

A one‑page summary of the extensions that scale the Aero Multi‑Tool from a
single‑machine source optimiser to a coordinator for multi‑million‑line,
multi‑language, absolute‑precision physics simulators.

## Design principles

1. **Backward compatibility.** Every new capability is opt‑in. Blueprints that
   omit the new sections produce identical behaviour; all 51 pre‑existing tests
   pass unchanged.
2. **Graceful degradation.** Heavy infrastructure (OpenBLAS, MPI, CUDA, an SSH/K8s
   cluster) is detected at runtime and lazy‑imported. When absent, the feature
   reports "unavailable" and the build continues locally. The tool never *requires*
   a GPU or a cluster.
3. **Two coherent config surfaces.** The human‑facing INI `blueprint.aero` and the
   engine‑facing `blueprint_config.json` both gain the same optional sections; the
   parser validates the INI form and surfaces it in the build context.

## What changed

| Area | Change | Key files |
|------|--------|-----------|
| Blueprint schema | Optional `[libraries]`, `[distributed]`, `[gpu]`, `[physics]`, `[precision_shield]` sections with validation + conservative defaults. | `blueprint_parser.py` |
| Multi‑language UAST | C/C++/Fortran tree‑sitter parsers; unified node kinds (`uast_function/call/global/type/gpu_kernel`); FFI detection for `extern "C"`, `cffi`/`ctypes`, Fortran `bind(c)`; `gpu_kernel` edges. | `src/analysis/semantic_mapper.py` |
| Library auto‑tuning | `LibraryTuner` detects BLAS/LAPACK/MPI/CUDA (pkg‑config → env → linker path) and emits flags; library choice added to the evolutionary genome. | `src/build/library_tuner.py`, `src/evolution/genetic_operators.py`, `src/evolution/bootstrap.py`, `src/hardware_profiling/profiler.py` |
| Strict floating‑point | Per‑compiler FP flag emission (GCC/Clang, Intel, rustc, nvcc) with global policy + per‑zone overrides. | `src/precision_shield/shield.py` |
| Distributed builds | `DistributedCoordinator` + Local/SSH/Kubernetes backends, shared cache (NFS/Redis/S3), retry + local fallback; dispatch wired into the sandbox manager. | `src/build/distributed.py`, `src/evolution/sandbox_manager.py` |
| GPU offloading | `GPUPipeline` plans/compiles CUDA/HIP kernels and produces a link plan; integrates FP flags. | `src/build/gpu_pipeline.py` |
| Physics invariants | `DimensionalAnalyzer` — heuristic dimensional analysis via a custom AST visitor (no CAS dependency). | `src/physics/units.py` |
| CLI | New subcommands `libraries`, `gpu`, `physics`; richer `analyze` stats. | `main.py` |
| Example + docs | Runnable mock simulator, expanded README, this summary. | `examples/physics_simulator/`, `README.md` |

## Data flow

```
blueprint.aero (INI)  ─┐                         ┌─ LibraryTuner ─→ linker/compiler flags
                       ├─ parser/validation ─────┤
blueprint_config.json ─┘        │                ├─ PrecisionShield ─→ FP flags (rustc/cc/nvcc)
                                ▼                 │
                        SemanticMapper ──→ UAST ──┼─ DimensionalAnalyzer ─→ unit warnings
                     (Py/Rust/C/C++/Fortran,      │
                      FFI + gpu_kernel edges)     ├─ GPUPipeline ─→ kernel objects + link plan
                                                  │
              Evolution genome (compiler knobs +  └─ DistributedCoordinator ─→ workers
              library choices) ──→ Pareto search        (local / SSH / K8s, shared cache)
```

## Testing

66 new tests cover each feature plus a performance‑regression suite (distributed
vs. single build time, strict‑FP reproducibility, cache hit‑rate after small
changes, large‑codebase scaling) and an acceptance suite mapped to the task's
criteria (mock simulator computes π to double precision; the shield blocks
constant‑folding of a sensitive constant; hardware profiling detects SIMD and
library paths). Total: **117 tests passing**.

## Deliberate trade‑offs

- **Heuristics over completeness.** Dimensional analysis and FFI detection are
  pragmatic heuristics tuned to catch obvious errors without false positives,
  not sound type systems.
- **Lazy optional deps.** `fabric`/`kubernetes` are pinned in `requirements.txt`
  but imported only when a remote backend is actually used, keeping the default
  install path light and the single‑machine path dependency‑free.
- **Simulated evaluation.** The evolutionary engine models compile/runtime cost
  (including library effects) rather than performing full physical compiles in
  the test environment; real workers execute the generated `BuildTask` commands.
