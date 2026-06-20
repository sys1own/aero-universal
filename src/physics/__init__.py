"""Physics-aware analysis passes for numerical simulation codebases.

Currently houses :mod:`src.physics.units`, a lightweight dimensional-analysis
pass that walks the Unified AST (or raw sources) and warns when arithmetic
expressions mix incompatible physical dimensions.
"""

from src.physics.units import Dimension, DimensionalAnalyzer, DimensionalWarning

__all__ = ["Dimension", "DimensionalAnalyzer", "DimensionalWarning"]
