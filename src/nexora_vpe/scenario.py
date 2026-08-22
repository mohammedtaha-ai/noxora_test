"""Validated scenario contract for the single S0 learning-mode case."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


ALLOWED_HISTORY_INTENTS = frozenset(
    {
        "PAIN_ONSET",
        "PAIN_LOCATION",
        "PAIN_RADIATION",
        "PAIN_SEVERITY",
        "ASSOCIATED_SYMPTOMS",
        "MECHANISM_OF_INJURY",
        "MEDICATIONS",
        "ALLERGIES",
        "PAST_MEDICAL_HISTORY",
        "ANTICOAGULANT_USE",
        "SUSPECT_INTERNAL_BLEEDING",
    }
)


@dataclass(frozen=True)
class InterventionDefinition:
    intervention_id: str
    pulse_compound: str
    volume_ml: float
    rate_ml_min: float

    def as_adapter_payload(self) -> dict[str, float | str]:
        return {
            "compound": self.pulse_compound,
            "volume_ml": self.volume_ml,
            "rate_ml_min": self.rate_ml_min,
        }


@dataclass(frozen=True)
class S0Scenario:
    scenario_id: str
    title: str
    pulse_revision: str
    patient_template: str
    hemorrhage_compartment: str
    hemorrhage_flow_rate_ml_min: float
    allowed_history_intents: frozenset[str]
    interventions: Mapping[str, InterventionDefinition]
    telemetry_keys: tuple[str, ...]
    mode: str = "learning"
    schema_version: str = "1.0"

    def validate(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("Unsupported scenario schema version")
        if self.mode != "learning":
            raise ValueError("S0 supports learning mode only")
        if self.patient_template != "adult_male_standard":
            raise ValueError("S0 only supports the pinned adult standard template")
        if self.hemorrhage_compartment != "Spleen":
            raise ValueError("S0 pathology must be the existing splenic hemorrhage")
        if self.hemorrhage_flow_rate_ml_min <= 0:
            raise ValueError("Existing hemorrhage flow rate must be positive")
        if not self.allowed_history_intents.issubset(ALLOWED_HISTORY_INTENTS):
            raise ValueError("Scenario contains an unknown history intent")
        if not self.interventions:
            raise ValueError("Scenario requires at least one constrained intervention")
        for definition in self.interventions.values():
            if definition.pulse_compound not in {"Saline", "PackedRBC"}:
                raise ValueError("S0 intervention maps to an unsupported Pulse compound")
            if definition.volume_ml <= 0 or definition.rate_ml_min <= 0:
                raise ValueError("Intervention volume and rate must be positive")

    def intervention(self, intervention_id: str) -> InterventionDefinition:
        try:
            return self.interventions[intervention_id]
        except KeyError as exc:
            raise ValueError(f"Intervention not allowed by scenario: {intervention_id}") from exc


def splenic_hemorrhage_learning_scenario() -> S0Scenario:
    scenario = S0Scenario(
        scenario_id="trauma_splenic_01",
        title="Abdominal trauma: active splenic hemorrhage",
        pulse_revision="e8a36497b8ba78e788dc201a6baf74e1c297c56f",
        patient_template="adult_male_standard",
        hemorrhage_compartment="Spleen",
        hemorrhage_flow_rate_ml_min=60.0,
        allowed_history_intents=frozenset(
            {"PAIN_ONSET", "PAIN_LOCATION", "MECHANISM_OF_INJURY", "SUSPECT_INTERNAL_BLEEDING"}
        ),
        interventions={
            "crystalloid_saline": InterventionDefinition(
                intervention_id="crystalloid_saline",
                pulse_compound="Saline",
                volume_ml=500.0,
                rate_ml_min=100.0,
            ),
            "blood_packed_rbc": InterventionDefinition(
                intervention_id="blood_packed_rbc",
                pulse_compound="PackedRBC",
                volume_ml=250.0,
                rate_ml_min=5.0,
            ),
        },
        telemetry_keys=(
            "heart_rate_bpm",
            "mean_arterial_pressure_mmhg",
            "blood_volume_ml",
            "total_hemorrhaged_volume_ml",
            "oxygen_saturation",
        ),
    )
    scenario.validate()
    return scenario
