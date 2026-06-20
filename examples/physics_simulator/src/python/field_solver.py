"""Field solver orchestration.

Demonstrates the FFI surface the Aero semantic mapper detects:

* a PyO3 call into the Rust core (``rust_relax_field``),
* a ``ctypes`` load of the legacy C library, and
* a fall-back pure-Python relaxation so the example runs with no toolchain.
"""

from __future__ import annotations

import ctypes
from typing import List


def _load_native():
    """Best-effort load of the compiled Rust/C core; ``None`` if unavailable."""
    try:
        return ctypes.CDLL("libphysics_core.so")
    except OSError:
        return None


def relax_field(grid: List[float], iterations: int = 100) -> List[float]:
    """Relax a 1-D field using a Jacobi sweep.

    Tries the native core first (PyO3 ``rust_relax_field`` / C ``c_relax``),
    then falls back to pure Python so results are always produced.
    """
    native = _load_native()
    if native is not None and hasattr(native, "c_relax"):
        # Real builds marshal the buffer; omitted in the mock.
        pass

    current = list(grid)
    for _ in range(iterations):
        nxt = list(current)
        for i in range(1, len(current) - 1):
            nxt[i] = 0.5 * (current[i - 1] + current[i + 1])
        current = nxt
    return current


def rust_relax_field(grid: List[float]) -> List[float]:
    """Placeholder mirroring the #[pyfunction] exported by the Rust core."""
    return relax_field(grid, iterations=1)
