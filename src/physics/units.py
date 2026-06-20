"""
Physics-Specific Invariant Checking -- dimensional analysis.

Implements a lightweight, heuristic dimensional-analysis pass.  It walks the
Unified AST (or raw Python sources), extracts arithmetic expressions, infers the
physical dimension of each quantity from declared annotations, and warns when an
expression mixes incompatible dimensions (e.g. adding a length to a time).

Quantities acquire dimensions from two sources:

1. The ``[physics] variable_dimensions`` blueprint mapping, e.g.
   ``{"dt": "time", "velocity": "length/time"}``.
2. Inline source annotations on assignments, e.g.::

       dt = 0.01        # [time]
       v  = dx / dt     # units: length/time

The pass is intentionally conservative: it only flags an expression when *both*
operands have a concretely known dimension that disagrees, so unknown
quantities never produce false positives.  It is a heuristic to catch obvious
errors, not a full type-checked unit system.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DimensionError(ValueError):
    """Raised internally when two dimensions cannot be combined."""


@dataclass(frozen=True)
class Dimension:
    """A physical dimension as a map of base unit -> integer/real exponent."""

    exponents: Tuple[Tuple[str, float], ...] = ()

    @classmethod
    def base(cls, unit: str) -> "Dimension":
        return cls(((unit, 1.0),))

    @classmethod
    def dimensionless(cls) -> "Dimension":
        return cls(())

    @classmethod
    def from_map(cls, mapping: Dict[str, float]) -> "Dimension":
        cleaned = tuple(sorted((u, e) for u, e in mapping.items() if abs(e) > 1e-9))
        return cls(cleaned)

    def as_map(self) -> Dict[str, float]:
        return dict(self.exponents)

    @property
    def is_dimensionless(self) -> bool:
        return len(self.exponents) == 0

    def __mul__(self, other: "Dimension") -> "Dimension":
        result = self.as_map()
        for unit, exp in other.exponents:
            result[unit] = result.get(unit, 0.0) + exp
        return Dimension.from_map(result)

    def __truediv__(self, other: "Dimension") -> "Dimension":
        result = self.as_map()
        for unit, exp in other.exponents:
            result[unit] = result.get(unit, 0.0) - exp
        return Dimension.from_map(result)

    def power(self, exponent: float) -> "Dimension":
        return Dimension.from_map({u: e * exponent for u, e in self.exponents})

    def __str__(self) -> str:
        if self.is_dimensionless:
            return "1"
        return "*".join(
            f"{u}^{e:g}" if e != 1 else u for u, e in self.exponents
        )


@dataclass
class DimensionalWarning:
    location: str
    message: str
    kind: str = "dimension_mismatch"

    def __str__(self) -> str:
        return f"{self.kind}:{self.location}: {self.message}"


# Transcendental functions whose arguments must be dimensionless.
_DIMENSIONLESS_ARG_FUNCS = {"sin", "cos", "tan", "exp", "log", "log10", "sinh", "cosh", "tanh"}


class DimensionalAnalyzer:
    """Heuristic dimensional-analysis pass over Python sources / the UAST."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        phys_cfg = self.config.get("physics", {}) or {}
        self.enabled = bool(phys_cfg.get("symbolic_validation", False))
        self.base_dimensions = list(phys_cfg.get("dimensions", []))
        # Optional explicit variable -> unit-expression declarations.
        self.declared: Dict[str, str] = dict(phys_cfg.get("variable_dimensions", {}))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_project(self, project_root: Path) -> List[DimensionalWarning]:
        """Analyse every Python source under ``project_root``."""
        if not self.enabled:
            return []
        warnings: List[DimensionalWarning] = []
        for py_file in sorted(Path(project_root).rglob("*.py")):
            warnings.extend(self.analyze_file(py_file))
        return warnings

    def analyze_uast(self, mapper_or_graph: Any) -> List[DimensionalWarning]:
        """Analyse the Python files referenced by a UAST graph."""
        if not self.enabled:
            return []
        graph = getattr(mapper_or_graph, "uast", mapper_or_graph)
        files: List[str] = []
        for _, data in graph.nodes(data=True):
            if data.get("language") != "python":
                continue
            loc = data.get("source_location") or []
            if loc and str(loc[0]).endswith(".py") and loc[0] not in files:
                files.append(loc[0])
        warnings: List[DimensionalWarning] = []
        for path in files:
            warnings.extend(self.analyze_file(Path(path)))
        return warnings

    def analyze_file(self, file_path: Path) -> List[DimensionalWarning]:
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except Exception:
            return []
        return self.analyze_source(source, str(file_path))

    def analyze_source(self, source: str, filename: str = "<source>") -> List[DimensionalWarning]:
        """Analyse a Python source string and return dimensional warnings."""
        if not self.enabled:
            return []
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError:
            return []

        annotations = self._scan_line_annotations(source)
        symbols: Dict[str, Dimension] = {}
        for name, expr in self.declared.items():
            dim = self._parse_unit_expression(expr)
            if dim is not None:
                symbols[name] = dim

        warnings: List[DimensionalWarning] = []
        self._visit(tree, filename, symbols, annotations, warnings)
        return warnings

    # ------------------------------------------------------------------
    # Unit-expression parsing ("length/time**2" -> Dimension)
    # ------------------------------------------------------------------

    def _parse_unit_expression(self, expr: str) -> Optional[Dimension]:
        expr = expr.strip()
        if not expr or expr in ("1", "dimensionless", "none"):
            return Dimension.dimensionless()
        try:
            node = ast.parse(expr, mode="eval").body
        except SyntaxError:
            return None
        try:
            return self._eval_unit_node(node)
        except DimensionError:
            return None

    def _eval_unit_node(self, node: ast.AST) -> Dimension:
        if isinstance(node, ast.Name):
            return Dimension.base(node.id)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Dimension.dimensionless()
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mult):
                return self._eval_unit_node(node.left) * self._eval_unit_node(node.right)
            if isinstance(node.op, ast.Div):
                return self._eval_unit_node(node.left) / self._eval_unit_node(node.right)
            if isinstance(node.op, ast.Pow):
                exponent = self._const_number(node.right)
                if exponent is None:
                    raise DimensionError("non-constant exponent in unit expression")
                return self._eval_unit_node(node.left).power(exponent)
        raise DimensionError("unsupported unit expression")

    # ------------------------------------------------------------------
    # AST traversal
    # ------------------------------------------------------------------

    def _visit(
        self,
        tree: ast.AST,
        filename: str,
        symbols: Dict[str, Dimension],
        annotations: Dict[int, str],
        warnings: List[DimensionalWarning],
    ) -> None:
        # First pass: register dimensions declared via inline annotations so
        # forward references inside the file still resolve.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target_name = self._assign_target_name(node)
                if not target_name:
                    continue
                ann = annotations.get(getattr(node, "lineno", -1))
                if ann:
                    dim = self._parse_unit_expression(ann)
                    if dim is not None:
                        symbols[target_name] = dim

        # Second pass: evaluate expressions and check assignment consistency.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is None:
                    continue
                loc = f"{filename}:{getattr(node, 'lineno', 0)}"
                rhs_dim = self._eval_expr(value, symbols, loc, warnings)
                target_name = self._assign_target_name(node)
                # A bare numeric literal (dimensionless RHS) *declares* the
                # quantity's units rather than violating them, so only flag a
                # mismatch when the RHS carries a concrete, non-trivial dimension.
                if (
                    target_name
                    and target_name in symbols
                    and rhs_dim is not None
                    and not rhs_dim.is_dimensionless
                ):
                    declared = symbols[target_name]
                    if declared != rhs_dim:
                        warnings.append(
                            DimensionalWarning(
                                location=loc,
                                message=(
                                    f"assignment to '{target_name}' expects [{declared}] "
                                    f"but expression has [{rhs_dim}]"
                                ),
                                kind="assignment_mismatch",
                            )
                        )
            elif isinstance(node, ast.Compare):
                loc = f"{filename}:{getattr(node, 'lineno', 0)}"
                self._eval_expr(node, symbols, loc, warnings)

    def _eval_expr(
        self,
        node: ast.AST,
        symbols: Dict[str, Dimension],
        loc: str,
        warnings: List[DimensionalWarning],
    ) -> Optional[Dimension]:
        """Infer a node's dimension, appending warnings on concrete conflicts.

        Returns ``None`` when the dimension is unknown (so callers don't treat
        an unknown as dimensionless).
        """
        if isinstance(node, ast.Constant):
            return Dimension.dimensionless() if isinstance(node.value, (int, float)) else None
        if isinstance(node, ast.Name):
            return symbols.get(node.id)
        if isinstance(node, ast.UnaryOp):
            return self._eval_expr(node.operand, symbols, loc, warnings)
        if isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left, symbols, loc, warnings)
            right = self._eval_expr(node.right, symbols, loc, warnings)
            return self._combine_binop(node, left, right, loc, warnings)
        if isinstance(node, ast.Compare):
            left = self._eval_expr(node.left, symbols, loc, warnings)
            for comparator in node.comparators:
                right = self._eval_expr(comparator, symbols, loc, warnings)
                if left is not None and right is not None and left != right:
                    warnings.append(
                        DimensionalWarning(
                            location=loc,
                            message=f"comparison between [{left}] and [{right}]",
                            kind="comparison_mismatch",
                        )
                    )
            return Dimension.dimensionless()
        if isinstance(node, ast.Call):
            return self._eval_call(node, symbols, loc, warnings)
        return None

    def _combine_binop(
        self,
        node: ast.BinOp,
        left: Optional[Dimension],
        right: Optional[Dimension],
        loc: str,
        warnings: List[DimensionalWarning],
    ) -> Optional[Dimension]:
        op = node.op
        if isinstance(op, (ast.Add, ast.Sub)):
            if left is not None and right is not None and left != right:
                warnings.append(
                    DimensionalWarning(
                        location=loc,
                        message=f"cannot {type(op).__name__.lower()} [{left}] and [{right}]",
                    )
                )
            return left if left is not None else right
        if isinstance(op, ast.Mult):
            return (left * right) if (left is not None and right is not None) else None
        if isinstance(op, ast.Div):
            return (left / right) if (left is not None and right is not None) else None
        if isinstance(op, ast.Pow):
            exponent = self._const_number(node.right)
            if left is not None and exponent is not None:
                return left.power(exponent)
            return None
        if isinstance(op, ast.Mod):
            return left
        return None

    def _eval_call(
        self,
        node: ast.Call,
        symbols: Dict[str, Dimension],
        loc: str,
        warnings: List[DimensionalWarning],
    ) -> Optional[Dimension]:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        arg_dims = [self._eval_expr(arg, symbols, loc, warnings) for arg in node.args]

        if func_name in _DIMENSIONLESS_ARG_FUNCS:
            for dim in arg_dims:
                if dim is not None and not dim.is_dimensionless:
                    warnings.append(
                        DimensionalWarning(
                            location=loc,
                            message=f"{func_name}() requires a dimensionless argument, got [{dim}]",
                            kind="transcendental_argument",
                        )
                    )
            return Dimension.dimensionless()
        if func_name in ("sqrt",):
            return arg_dims[0].power(0.5) if arg_dims and arg_dims[0] is not None else None
        if func_name in ("abs", "fabs", "min", "max"):
            return arg_dims[0] if arg_dims else None
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _const_number(node: ast.AST) -> Optional[float]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = DimensionalAnalyzer._const_number(node.operand)
            return -inner if inner is not None else None
        return None

    @staticmethod
    def _assign_target_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        return None

    @staticmethod
    def _scan_line_annotations(source: str) -> Dict[int, str]:
        """Map line number -> declared unit expression from trailing comments.

        Recognised forms (case-insensitive)::

            x = ...  # [length/time]
            x = ...  # units: length/time
            x = ...  # dim: length
        """
        annotations: Dict[int, str] = {}
        pattern = re.compile(
            r"#\s*(?:\[(?P<bracket>[^\]]+)\]|(?:units|dim|dimension)\s*[:=]\s*(?P<kv>[^#]+))",
            re.IGNORECASE,
        )
        for lineno, line in enumerate(source.splitlines(), start=1):
            match = pattern.search(line)
            if match:
                expr = (match.group("bracket") or match.group("kv") or "").strip()
                if expr:
                    annotations[lineno] = expr
        return annotations
