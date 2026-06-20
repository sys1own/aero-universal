"""Fundamental physical constants.

This module is registered as an ``absolute_immutable`` Precision Shield zone:
the compiler must not constant-fold, reorder, or otherwise perturb these values.
The shield validates that no transformation alters their bit-exact
representation -- see ``blueprint_config.json``.
"""

# Ratio of a circle's circumference to its diameter (double precision).
PI = 3.141592653589793

# Speed of light in vacuum (m/s, exact by SI definition).
SPEED_OF_LIGHT = 299792458.0

# Planck constant (J*s, exact by SI definition).
PLANCK = 6.62607015e-34

# Boltzmann constant (J/K, exact by SI definition).
BOLTZMANN = 1.380649e-23
