"""Genetic operators for the self-evolution engine: mutation and crossover."""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List

import numpy as np


class MutationEngine:
    """Applies random mutations to an individual's genome."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        evo = config.get("project", {}).get("evolutionary_bootstrap", {})
        # Copy so library genes can be appended without mutating shared config.
        self.mutation_vectors = dict(evo.get("mutation_vectors", {}))
        self.mutation_rate = 0.3
        self.library_genes: List[str] = []
        self.framework_genes: List[str] = []
        self._add_library_genes(config)
        self._add_framework_genes(config)

    def _add_library_genes(self, config: Dict[str, Any]) -> None:
        """Fold numerical-library choices into the genome (feature #2).

        When a ``[libraries]`` section is present, each tunable library becomes a
        categorical gene so the evolutionary engine can search combinations of
        BLAS/LAPACK/MPI/CUDA backends alongside the compiler knobs.
        """
        lib = config.get("libraries")
        if not isinstance(lib, dict):
            return

        genes: Dict[str, List[str]] = {}
        for key in ("blas", "lapack"):
            choice = str(lib.get(key, "none")).lower()
            if choice == "none":
                continue
            genes[key] = ["mkl", "openblas", "none"] if choice == "auto" else [choice, "none"]
        if lib.get("mpi"):
            flavor = lib.get("mpi_flavor")
            genes["mpi_flavor"] = [flavor, "none"] if flavor else ["openmpi", "mpich", "none"]
        if str(lib.get("cuda", "none")).lower() != "none":
            genes["cuda"] = ["auto", "none"]

        for key, values in genes.items():
            deduped: List[str] = []
            for v in values:
                if v not in deduped:
                    deduped.append(v)
            self.mutation_vectors[key] = deduped
            self.library_genes.append(key)

    def _add_framework_genes(self, config: Dict[str, Any]) -> None:
        """Fold physics-framework versions into the genome (feature #4).

        When a framework lists several candidate ``versions`` the engine may
        search them for the best performance.
        """
        if not config.get("frameworks"):
            return
        try:
            from src.build.framework_integration import FrameworkIntegration

            space = FrameworkIntegration(config).genome_space()
        except Exception:
            return
        for key, values in space.items():
            self.mutation_vectors[key] = list(values)
            self.framework_genes.append(key)

    def apply_mutations(self, workspace: Any, genome: Dict[str, Any]) -> Dict[str, Any]:
        """Return the workspace path unchanged (mutations are config-level, not source-level)."""
        return workspace

    def mutate(self, genome: Dict[str, Any]) -> Dict[str, Any]:
        mutated = copy.deepcopy(genome)
        for key, spec in self.mutation_vectors.items():
            if random.random() > self.mutation_rate:
                continue
            if isinstance(spec, dict) and "range" in spec:
                low, high = spec["range"]
                step = spec.get("step", 1)
                values = list(range(low, high + 1, step))
                if values:
                    mutated[key] = random.choice(values)
            elif isinstance(spec, list) and spec:
                mutated[key] = random.choice(spec)
        return mutated

    def generate_random(self) -> Dict[str, Any]:
        genome: Dict[str, Any] = {}
        for key, spec in self.mutation_vectors.items():
            if isinstance(spec, dict) and "range" in spec:
                low, high = spec["range"]
                step = spec.get("step", 1)
                values = list(range(low, high + 1, step))
                genome[key] = random.choice(values) if values else spec.get("default", low)
            elif isinstance(spec, list) and spec:
                genome[key] = random.choice(spec)
            else:
                genome[key] = spec
        return genome


class CrossoverEngine:
    """Performs crossover between two parent genomes."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def crossover(self, parent_a: Dict[str, Any], parent_b: Dict[str, Any]) -> Dict[str, Any]:
        child: Dict[str, Any] = {}
        all_keys = set(parent_a.keys()) | set(parent_b.keys())
        for key in all_keys:
            if key in parent_a and key in parent_b:
                child[key] = parent_a[key] if random.random() < 0.5 else parent_b[key]
            elif key in parent_a:
                child[key] = parent_a[key]
            else:
                child[key] = parent_b[key]
        return child
