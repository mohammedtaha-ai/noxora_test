"""Physiology boundary for the S0 runtime.

`DeterministicPhysiologyAdapter` is a test double for runtime verification, not
a clinical physiology model. Production wiring must use a pinned Pulse adapter
and preserve the same narrow contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from .scenario import S0Scenario


class PhysiologyAdapter(ABC):
    """Single-owner boundary through which the runtime accesses physiology."""

    @property
    @abstractmethod
    def engine_version(self) -> str:
        """Return the exact engine or adapter revision used for a run."""

    @property
    @abstractmethod
    def simulation_time_s(self) -> float:
        """Return engine simulation time, never wall-clock time."""

    @abstractmethod
    def bootstrap(self, scenario: S0Scenario) -> None:
        """Initialize the pre-existing scenario pathology."""

    @abstractmethod
    def advance(self, duration_s: float) -> None:
        """Advance only by a positive duration owned by the VPE clock."""

    @abstractmethod
    def apply_intervention(self, payload: Mapping[str, Any]) -> None:
        """Apply a constrained, already-validated intervention payload."""

    @abstractmethod
    def telemetry(self, requested_keys: tuple[str, ...]) -> Mapping[str, float]:
        """Return only scenario-approved telemetry keys."""

    @abstractmethod
    def save_state(self) -> Mapping[str, Any]:
        """Return a serializable state owned by the adapter implementation."""

    @abstractmethod
    def restore_state(self, state: Mapping[str, Any]) -> None:
        """Restore a state previously emitted by this adapter revision."""


@dataclass
class _Infusion:
    compound: str
    remaining_ml: float
    rate_ml_min: float


@dataclass
class DeterministicPhysiologyAdapter(PhysiologyAdapter):
    """Minimal deterministic test double for orchestration and contract tests.

    It deliberately exposes no diagnosis, recommendation, or patient-specific
    interpretation. Numeric behavior simply provides stable monotonic telemetry
    for testing the VPE command, event, and snapshot flow.
    """

    _engine_version: str = "deterministic-test-double/1.0"
    _time_s: float = 0.0
    _blood_volume_ml: float = 5489.0
    _hemorrhage_flow_ml_s: float = 0.0
    _total_hemorrhage_ml: float = 0.0
    _infusions: list[_Infusion] = field(default_factory=list)
    _bootstrapped: bool = False

    @property
    def engine_version(self) -> str:
        return self._engine_version

    @property
    def simulation_time_s(self) -> float:
        return self._time_s

    def bootstrap(self, scenario: S0Scenario) -> None:
        scenario.validate()
        self._time_s = 0.0
        self._blood_volume_ml = 5489.0
        self._hemorrhage_flow_ml_s = scenario.hemorrhage_flow_rate_ml_min / 60.0
        self._total_hemorrhage_ml = 0.0
        self._infusions = []
        self._bootstrapped = True

    def advance(self, duration_s: float) -> None:
        if not self._bootstrapped:
            raise RuntimeError("Adapter must be bootstrapped before advancing")
        if duration_s <= 0:
            raise ValueError("Simulation duration must be positive")
        remaining_s = duration_s
        while remaining_s > 0:
            step_s = min(1.0, remaining_s)
            hemorrhage_ml = self._hemorrhage_flow_ml_s * step_s
            infusion_ml = 0.0
            next_infusions: list[_Infusion] = []
            for infusion in self._infusions:
                delivered = min(infusion.remaining_ml, infusion.rate_ml_min / 60.0 * step_s)
                infusion_ml += delivered
                remaining_volume = infusion.remaining_ml - delivered
                if remaining_volume > 1e-9:
                    next_infusions.append(
                        _Infusion(
                            compound=infusion.compound,
                            remaining_ml=remaining_volume,
                            rate_ml_min=infusion.rate_ml_min,
                        )
                    )
            self._infusions = next_infusions
            self._blood_volume_ml += infusion_ml - hemorrhage_ml
            self._total_hemorrhage_ml += hemorrhage_ml
            self._time_s += step_s
            remaining_s -= step_s

    def apply_intervention(self, payload: Mapping[str, Any]) -> None:
        if not self._bootstrapped:
            raise RuntimeError("Adapter must be bootstrapped before interventions")
        compound = payload.get("compound")
        volume_ml = payload.get("volume_ml")
        rate_ml_min = payload.get("rate_ml_min")
        if compound not in {"Saline", "PackedRBC"}:
            raise ValueError("Unsupported test-double compound")
        if not isinstance(volume_ml, (int, float)) or volume_ml <= 0:
            raise ValueError("Intervention volume must be positive")
        if not isinstance(rate_ml_min, (int, float)) or rate_ml_min <= 0:
            raise ValueError("Intervention rate must be positive")
        self._infusions.append(
            _Infusion(compound=str(compound), remaining_ml=float(volume_ml), rate_ml_min=float(rate_ml_min))
        )

    def telemetry(self, requested_keys: tuple[str, ...]) -> Mapping[str, float]:
        if not self._bootstrapped:
            raise RuntimeError("Adapter must be bootstrapped before telemetry")
        loss_fraction = max(0.0, min(0.95, self._total_hemorrhage_ml / 5489.0))
        available = {
            "heart_rate_bpm": round(72.0 + 120.0 * loss_fraction, 4),
            "mean_arterial_pressure_mmhg": round(max(40.0, 95.3 - 30.0 * loss_fraction), 4),
            "blood_volume_ml": round(self._blood_volume_ml, 4),
            "total_hemorrhaged_volume_ml": round(self._total_hemorrhage_ml, 4),
            "oxygen_saturation": round(max(0.80, 0.974 - 0.05 * loss_fraction), 6),
        }
        unknown = set(requested_keys).difference(available)
        if unknown:
            raise ValueError(f"Requested unknown telemetry: {sorted(unknown)}")
        return {key: available[key] for key in requested_keys}

    def save_state(self) -> Mapping[str, Any]:
        return deepcopy(
            {
                "engine_version": self.engine_version,
                "time_s": self._time_s,
                "blood_volume_ml": self._blood_volume_ml,
                "hemorrhage_flow_ml_s": self._hemorrhage_flow_ml_s,
                "total_hemorrhage_ml": self._total_hemorrhage_ml,
                "infusions": [infusion.__dict__ for infusion in self._infusions],
                "bootstrapped": self._bootstrapped,
            }
        )

    def restore_state(self, state: Mapping[str, Any]) -> None:
        if state.get("engine_version") != self.engine_version:
            raise ValueError("Snapshot belongs to a different adapter revision")
        if not state.get("bootstrapped"):
            raise ValueError("Cannot restore an unbootstrapped adapter state")
        self._time_s = float(state["time_s"])
        self._blood_volume_ml = float(state["blood_volume_ml"])
        self._hemorrhage_flow_ml_s = float(state["hemorrhage_flow_ml_s"])
        self._total_hemorrhage_ml = float(state["total_hemorrhage_ml"])
        self._infusions = [_Infusion(**dict(item)) for item in state["infusions"]]
        self._bootstrapped = True
