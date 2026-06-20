"""Top-level orchestration for the mock physics simulator.

Running ``python -m src.python.orchestrator`` (from the example root) produces a
result dict including PI computed to double precision -- the simple validation
target referenced by the Aero acceptance criteria.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from src.python.constants import PI
from src.python.field_solver import relax_field
from src.python.integrators import machin_pi


def validate_pi() -> Dict[str, Any]:
    """Validate that the simulator reproduces PI to double precision."""
    computed = machin_pi()
    return {
        "computed_pi": computed,
        "reference_pi": PI,
        "matches_double_precision": math.isclose(computed, math.pi, rel_tol=0.0, abs_tol=1e-15),
    }


def run_simulation() -> Dict[str, Any]:
    field = [0.0] + [1.0] * 8 + [0.0]
    relaxed = relax_field(field, iterations=50)
    pi_check = validate_pi()
    return {
        "pi": pi_check,
        "field_endpoints": (relaxed[0], relaxed[-1]),
        "field_energy": sum(x * x for x in relaxed),
    }


def main() -> int:
    result = run_simulation()
    print("Physics simulator result:")
    print(f"  computed pi : {result['pi']['computed_pi']!r}")
    print(f"  matches f64 : {result['pi']['matches_double_precision']}")
    print(f"  field energy: {result['field_energy']:.6f}")
    return 0 if result["pi"]["matches_double_precision"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
