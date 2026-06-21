# -*- coding: utf-8 -*-
"""Tests for AST-driven modular decomposition (``decomposition_mode``).

Layers:
* ``TestModularDecomposer``      -- direct AST extraction, imports, orchestrator.
* ``TestDecomposerErrors``       -- missing nodes / collisions / bad input.
* ``TestEngineModular``          -- ScaffoldEngine 'modular_package' routing.
* ``TestPipelineModular``        -- blueprint-driven decomposition pipeline.
* ``TestParserModuleMapping``    -- [scaffold] module_mapping / decomposition_mode.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from blueprint_parser import BlueprintParseError, normalize_optional_sections
from src.scaffold import ScaffoldEngine
from src.scaffold.decomposition import (
    DecompositionError,
    ImportCollisionError,
    MissingASTNodeError,
    ModularDecomposer,
)
from src.scaffold.pipeline import ScaffoldBuildPipeline

MONOLITH = '''\
# -*- coding: utf-8 -*-
"""A monolithic script to be decomposed."""
from __future__ import annotations
import os
import json

GLOBAL_CONST = 42


class SchemaValidator:
    """Validate things."""

    def check(self, blob):
        return json.dumps(blob)


@staticmethod
def shield(value):
    return os.fspath(value)


def parse_blueprint(text):
    return SchemaValidator().check({"text": text})


def main():
    return parse_blueprint("hello")
'''


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)


# ---------------------------------------------------------------------------
# Direct decomposer
# ---------------------------------------------------------------------------


class TestModularDecomposer(_Tmp):
    def _decompose(self, mapping, **kwargs):
        dest = self.tmp / "dist"
        decomposer = ModularDecomposer(verbose=False)
        result = decomposer.decompose(
            MONOLITH, mapping, source_filename="main.py", dest_dir=dest, **kwargs
        )
        return dest, result

    def test_extracts_classes_and_functions_into_targets(self):
        dest, result = self._decompose(
            {"parser": ["SchemaValidator", "parse_blueprint"], "shielder": ["shield"]}
        )
        self.assertTrue((dest / "parser.py").exists())
        self.assertTrue((dest / "shielder.py").exists())
        parser_src = (dest / "parser.py").read_text()
        self.assertIn("class SchemaValidator", parser_src)
        self.assertIn("def parse_blueprint", parser_src)
        self.assertIn("def shield", (dest / "shielder.py").read_text())
        # parse_blueprint did not leak into the shielder module.
        self.assertNotIn("parse_blueprint", (dest / "shielder.py").read_text())

    def test_decorators_are_preserved_during_extraction(self):
        dest, _ = self._decompose({"shielder": ["shield"]})
        self.assertIn("@staticmethod", (dest / "shielder.py").read_text())

    def test_global_imports_duplicated_into_every_module(self):
        dest, _ = self._decompose(
            {"parser": ["SchemaValidator"], "shielder": ["shield"]}
        )
        for name in ("parser.py", "shielder.py"):
            text = (dest / name).read_text()
            self.assertIn("import os", text)
            self.assertIn("import json", text)
            self.assertIn("from __future__ import annotations", text)
            # __future__ must precede any other import.
            self.assertLess(text.index("from __future__"), text.index("import os"))

    def test_generates_empty_package_init(self):
        dest, result = self._decompose({"parser": ["SchemaValidator"]})
        init = dest / "__init__.py"
        self.assertTrue(init.exists())
        self.assertEqual(init.read_text(), "")
        self.assertEqual(result.package_init, "__init__.py")

    def test_orchestrator_rewrites_internal_imports(self):
        dest, result = self._decompose(
            {"parser": ["SchemaValidator", "parse_blueprint"], "shielder": ["shield"]}
        )
        main_src = (dest / "main.py").read_text()
        self.assertIn("from .parser import SchemaValidator, parse_blueprint", main_src)
        self.assertIn("from .shielder import shield", main_src)
        # Moved defs are gone from the orchestrator, but the non-mapped code stays.
        self.assertNotIn("class SchemaValidator", main_src)
        self.assertNotIn("def parse_blueprint", main_src)
        self.assertIn("GLOBAL_CONST = 42", main_src)
        self.assertIn("def main():", main_src)

    def test_orchestrator_preserves_module_docstring_first(self):
        dest, _ = self._decompose({"parser": ["SchemaValidator"]})
        main_src = (dest / "main.py").read_text()
        # __future__ stays ahead of the generated import block.
        self.assertLess(
            main_src.index("from __future__"),
            main_src.index("from .parser import"),
        )

    def test_all_generated_files_are_syntactically_valid(self):
        import ast as _ast

        dest, result = self._decompose(
            {"parser": ["SchemaValidator", "parse_blueprint"], "shielder": ["shield"]}
        )
        for name in result.files:
            _ast.parse((dest / name).read_text())  # raises on bad syntax

    def test_filename_normalization_accepts_dot_py(self):
        dest, _ = self._decompose({"parser.py": ["SchemaValidator"]})
        self.assertTrue((dest / "parser.py").exists())

    def test_result_to_dict_reports_structure(self):
        _, result = self._decompose(
            {"parser": ["SchemaValidator", "parse_blueprint"]}
        )
        data = result.to_dict()
        self.assertEqual(data["mode"], "modular_package")
        self.assertIn("__init__.py", data["files"])
        module = next(m for m in data["modules"] if m["filename"] == "parser.py")
        self.assertEqual(module["classes"], ["SchemaValidator"])
        self.assertEqual(module["functions"], ["parse_blueprint"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDecomposerErrors(_Tmp):
    def _run(self, source, mapping):
        ModularDecomposer(verbose=False).decompose(
            source, mapping, dest_dir=self.tmp / "out"
        )

    def test_missing_ast_node_raises(self):
        with self.assertRaises(MissingASTNodeError):
            self._run(MONOLITH, {"parser": ["DoesNotExist"]})

    def test_cross_module_collision_raises(self):
        with self.assertRaises(ImportCollisionError):
            self._run(MONOLITH, {"a": ["SchemaValidator"], "b": ["SchemaValidator"]})

    def test_empty_mapping_raises(self):
        with self.assertRaises(DecompositionError):
            self._run(MONOLITH, {})

    def test_unparseable_source_raises(self):
        with self.assertRaises(DecompositionError):
            self._run("def broken(:\n", {"x": ["broken"]})

    def test_init_target_is_rejected(self):
        with self.assertRaises(DecompositionError):
            self._run(MONOLITH, {"__init__": ["SchemaValidator"]})


# ---------------------------------------------------------------------------
# Engine routing
# ---------------------------------------------------------------------------


class TestEngineModular(_Tmp):
    def test_engine_routes_to_modular_decomposition(self):
        src = self.tmp / "main.py"
        src.write_text(MONOLITH)
        dist = self.tmp / "pkg"
        msgs = []
        engine = ScaffoldEngine(logger=msgs.append, verbose=True)
        result = engine.scaffold(
            source_entry=str(src),
            distribution_directory=dist,
            language="python",
            module_mapping={"parser": ["SchemaValidator", "parse_blueprint"]},
            decomposition_mode="modular_package",
            build=True,
        )
        self.assertEqual(result.language, "python")
        self.assertTrue((dist / "parser.py").exists())
        self.assertTrue((dist / "__init__.py").exists())
        self.assertIn("decomposition", result.repo)
        self.assertTrue(result.build["succeeded"])
        # Structured decomposition logs surfaced.
        joined = "\n".join(msgs)
        self.assertIn("[Decomposing] Extracted class 'SchemaValidator'", joined)
        self.assertIn("[Scaffold   ] Initialized package boundary __init__.py", joined)

    def test_engine_without_mode_uses_plain_python_layout(self):
        src = self.tmp / "main.py"
        src.write_text(MONOLITH)
        dist = self.tmp / "plain"
        result = ScaffoldEngine().scaffold(
            source_entry=str(src),
            distribution_directory=dist,
            language="python",
        )
        # Single-file copy, not a decomposed package.
        self.assertTrue((dist / "pyproject.toml").exists())
        self.assertFalse((dist / "__init__.py").exists())


# ---------------------------------------------------------------------------
# Blueprint pipeline
# ---------------------------------------------------------------------------


class TestPipelineModular(_Tmp):
    def test_pipeline_decomposes_from_blueprint_context(self):
        src = self.tmp / "main.py"
        src.write_text(MONOLITH)
        dist = self.tmp / "dist"
        context = {
            "frameworks": {"language": "python"},
            "scaffold": {
                "source_entry": str(src),
                "distribution_directory": str(dist),
                "decomposition_mode": "modular_package",
                "module_mapping": {
                    "parser": ["SchemaValidator", "parse_blueprint"],
                    "shielder": ["shield"],
                },
            },
        }
        pipeline = ScaffoldBuildPipeline(logger=lambda _m: None, verbose=False)
        result = pipeline.run(context, build=True)
        self.assertTrue(result.succeeded)
        self.assertTrue((dist / "parser.py").exists())
        self.assertTrue((dist / "shielder.py").exists())
        self.assertTrue((dist / "__init__.py").exists())
        self.assertIn(
            "from .parser import SchemaValidator", (dist / "main.py").read_text()
        )


# ---------------------------------------------------------------------------
# Blueprint parser
# ---------------------------------------------------------------------------


class TestParserModuleMapping(unittest.TestCase):
    def test_module_mapping_and_mode_parsed(self):
        normalized = normalize_optional_sections(
            {
                "scaffold": {
                    "source_entry": "main.py",
                    "decomposition_mode": "modular_package",
                    "module_mapping": {
                        "parser": ["SchemaValidator", "parse_blueprint"],
                        "cli": "main, create_parser",
                    },
                }
            }
        )
        scaffold = normalized["scaffold"]
        self.assertEqual(scaffold["decomposition_mode"], "modular_package")
        self.assertEqual(
            scaffold["module_mapping"]["parser"],
            ["SchemaValidator", "parse_blueprint"],
        )
        # Comma-separated string values are normalised to lists.
        self.assertEqual(scaffold["module_mapping"]["cli"], ["main", "create_parser"])

    def test_unknown_mode_rejected(self):
        with self.assertRaises(BlueprintParseError):
            normalize_optional_sections(
                {"scaffold": {"decomposition_mode": "teleport"}}
            )

    def test_defaults_when_absent(self):
        normalized = normalize_optional_sections({})
        self.assertEqual(normalized["scaffold"]["decomposition_mode"], "")
        self.assertEqual(normalized["scaffold"]["module_mapping"], {})


if __name__ == "__main__":
    unittest.main()
