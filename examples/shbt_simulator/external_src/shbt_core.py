"""SHBT simulator core (as imported from an external repository).

This file is deliberately written the way real imported code often arrives:
with a missing import (``math``), an unused import (``sys``), and an
un-annotated helper.  Aero's context-ingestion repair rules fix all three when
this tree is ingested via the ``[context]`` blueprint section.
"""

import os
import sys


def baryogenesis_rate(temperature, coupling):
    # Uses math.exp without importing math -> auto_import adds the import.
    return coupling * math.exp(-1.0 / temperature)


def relic_abundance(cross_section, hubble):
    return hubble / (cross_section + 1.0e-30)


def write_checkpoint(state):
    # No value return -> type_inference annotates the return as None.
    path = os.path.join(".aero", "shbt_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
