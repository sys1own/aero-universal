# Mock Physics Simulator (Aero example)

A minimal multi-language project that exercises every physics-scale capability of
the Aero Multi-Tool from a single `blueprint.aero`.

## Layout

```
examples/physics_simulator/
├── blueprint.aero            # INI blueprint (all optional sections)
├── blueprint_config.json     # JSON config consumed by the engines
└── src/
    ├── python/               # orchestration (PyO3 + ctypes call sites)
    │   ├── constants.py       # Precision-Shield "absolute_immutable" zone
    │   ├── integrators.py     # dimension-annotated time integrators
    │   ├── field_solver.py    # FFI surface + pure-Python fallback
    │   └── orchestrator.py    # entry point; validates pi to double precision
    ├── native/lib.rs          # Rust core: #[pyfunction] + extern "C"
    ├── c/legacy_solver.c      # C legacy: typedef, global, extern binding
    ├── fortran/legacy_kernels.f90  # Fortran with bind(c) interfaces
    └── kernels/reduce.cu      # CUDA kernels + launch site
```

## Run it

```bash
cd examples/physics_simulator

# 1. Validate the simulator output (computes pi to double precision)
python3 -m src.python.orchestrator

# 2. Cross-language UAST + FFI detection
python3 ../../main.py analyze   --workspace . --config blueprint_config.json

# 3. Heuristic dimensional analysis (clean -> 0 warnings)
python3 ../../main.py physics   --workspace . --config blueprint_config.json

# 4. Numerical-library detection + linker flags
python3 ../../main.py libraries --config blueprint_config.json

# 5. GPU kernel compilation plan (skips gracefully without nvcc)
python3 ../../main.py gpu       --workspace . --config blueprint_config.json

# 6. Precision-shield validation of the sensitive-constant zone
python3 ../../main.py shield    --workspace . --config blueprint_config.json
```

Everything degrades gracefully: with no OpenBLAS, MPI, CUDA toolkit, or build
cluster installed, the analysis still runs and the simulator still computes the
correct answer on a single machine.
