"""Nexora VPE S0 headless runtime.

The package records structured learning-simulation evidence. It does not offer
clinical decision support, patient-specific diagnosis, treatment advice, or
high-stakes assessment.
"""

from .adapter import DeterministicPhysiologyAdapter, PhysiologyAdapter
from .runtime import VpeRuntime
from .scenario import S0Scenario
from .scenario_io import load_s0_scenario

__all__ = [
    "DeterministicPhysiologyAdapter",
    "PhysiologyAdapter",
    "S0Scenario",
    "VpeRuntime",
    "load_s0_scenario",
]
