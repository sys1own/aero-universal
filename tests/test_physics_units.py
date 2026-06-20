"""Tests for physics dimensional analysis (feature #6)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.physics.units import Dimension, DimensionalAnalyzer

_CFG = {
    "physics": {
        "symbolic_validation": True,
        "dimensions": ["length", "time", "mass"],
        "variable_dimensions": {"g": "length/time**2"},
    }
}


class TestDimensionAlgebra(unittest.TestCase):
    def test_mul_div_pow(self):
        length = Dimension.base("length")
        time = Dimension.base("time")
        velocity = length / time
        self.assertEqual(velocity.as_map(), {"length": 1.0, "time": -1.0})
        accel = velocity / time
        self.assertEqual(accel.as_map(), {"length": 1.0, "time": -2.0})
        area = length.power(2)
        self.assertEqual(area.as_map(), {"length": 2.0})
        self.assertTrue((length / length).is_dimensionless)


class TestDimensionalAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = DimensionalAnalyzer(_CFG)

    def test_clean_code_no_warnings(self):
        src = (
            "dt = 0.01        # [time]\n"
            "dx = 1.0         # [length]\n"
            "speed = dx / dt  # units: length/time\n"
            "fall = g * dt    # units: length/time\n"
        )
        self.assertEqual(self.analyzer.analyze_source(src, "c.py"), [])

    def test_add_mismatch_detected(self):
        src = "dt = 1.0  # [time]\ndx = 1.0  # [length]\nbad = dx + dt\n"
        warns = self.analyzer.analyze_source(src, "m.py")
        self.assertTrue(any(w.kind == "dimension_mismatch" for w in warns))

    def test_assignment_mismatch_detected(self):
        src = "dx = 1.0  # [length]\nenergy = dx  # units: mass*length**2/time**2\n"
        warns = self.analyzer.analyze_source(src, "m.py")
        self.assertTrue(any(w.kind == "assignment_mismatch" for w in warns))

    def test_transcendental_argument(self):
        src = "import math\ndx = 1.0  # [length]\np = math.sin(dx)\n"
        warns = self.analyzer.analyze_source(src, "m.py")
        self.assertTrue(any(w.kind == "transcendental_argument" for w in warns))

    def test_literal_declaration_not_flagged(self):
        # Declaring a constant's units must not be a violation.
        src = "dt = 0.01  # [time]\n"
        self.assertEqual(self.analyzer.analyze_source(src, "m.py"), [])

    def test_unknown_quantities_no_false_positive(self):
        src = "result = foo + bar\n"  # both unknown -> no warning
        self.assertEqual(self.analyzer.analyze_source(src, "m.py"), [])

    def test_disabled_returns_nothing(self):
        disabled = DimensionalAnalyzer({"physics": {"symbolic_validation": False}})
        src = "dt = 1.0  # [time]\ndx = 1.0  # [length]\nbad = dx + dt\n"
        self.assertEqual(disabled.analyze_source(src, "m.py"), [])

    def test_analyze_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.py").write_text("dt = 1.0  # [time]\nx = dt + dt\n")
            (root / "bad.py").write_text("dt = 1.0  # [time]\ndx = 1.0  # [length]\nb = dx + dt\n")
            warns = self.analyzer.analyze_project(root)
            self.assertTrue(any("bad.py" in w.location for w in warns))


if __name__ == "__main__":
    unittest.main()
