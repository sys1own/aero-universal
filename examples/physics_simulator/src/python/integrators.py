"""Time-integration cores (protected ``invariant_preservation`` zone).

The integrators below are dimension-annotated so the Aero dimensional-analysis
pass can verify them.  Each line documents the physical dimension of its result.
"""

from src.python.constants import PI


def leibniz_pi(terms: int = 5_000_000) -> float:
    """Compute PI via the Leibniz series (dimensionless, converges slowly)."""
    total = 0.0
    sign = 1.0
    for k in range(terms):
        total += sign / (2.0 * k + 1.0)
        sign = -sign
    return 4.0 * total


def machin_pi() -> float:
    """Compute PI via Machin's formula -- fast, double-precision accurate."""
    import math

    return 16.0 * math.atan(1.0 / 5.0) - 4.0 * math.atan(1.0 / 239.0)


def euler_step(position: float, velocity: float, dt: float) -> float:
    """Advance position by one explicit-Euler step.

    Dimensionally: [length] + [length/time] * [time] = [length].
    """
    dx = velocity * dt          # units: length
    return position + dx        # units: length


def free_fall_velocity(g: float, dt: float) -> float:
    """Velocity gained falling under gravity g for time dt -> [length/time]."""
    return g * dt               # units: length/time
