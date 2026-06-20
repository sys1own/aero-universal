# SHBT Simulator (JSON-blueprint + context-ingestion example)

A mixed-language project assembled **from a single JSON `blueprint.aero`** that
imports its core from an external source tree and repairs it on the way in.

## Layout

```
examples/shbt_simulator/
├── blueprint.aero          # JSON blueprint (all required sections + [context])
└── external_src/
    └── shbt_core.py        # "external" code with a missing/unused import + un-annotated fn
```

## Run it

```bash
cd examples/shbt_simulator

# 1. Ingest the external source tree and apply repair rules.
#    -> copies external_src/ into src/python/shbt/ and writes
#       context_analysis_report.json
python ../../main.py ingest --workspace . --config blueprint.aero

# 2. Inspect what was imported/repaired
cat context_analysis_report.json

# 3. Precision-shield validation of the protected zone
python ../../main.py shield --workspace . --config blueprint.aero
```

After step 1, `src/python/shbt/shbt_core.py` has `import math` added,
`import sys` removed, and `write_checkpoint` annotated `-> None` — and the file
still parses (repairs are rolled back if they would break syntax).

The JSON blueprint also exercises every other section (precision/quad zones,
hardware profiling, memoization, libraries, HPC, physics dimensions, frameworks,
runtime, validation), all of which degrade gracefully on a single machine.
