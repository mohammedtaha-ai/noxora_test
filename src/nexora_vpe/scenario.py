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
    }
)

ALLOWED_CLINICAL_HYPOTHESES = frozenset({"INTERNAL_BLEEDING"})
BUILT_IN_OBSERVATION_IDS = frozenset({"VITALS"})


@dataclass(frozen=True)
class ObservationDefinition:
    observation_id: str
    enabled: bool
    controlled_finding: str | None = None


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
class EscalationDefinition:
    """A scenario-authored, non-physiology escalation option.

    The identifier is authoritative evidence only. It neither changes Pulse state
    nor represents a real-world recommendation, disposition, or clinical outcome.
    """

    escalation_id: str


@dataclass(frozen=True)
class S0Scenario:
    scenario_id: str
    title: str
    pulse_revision: str
    patient_template: str
    hemorrhage_compartment: str
    hemorrhage_flow_rate_ml_min: float
    learning_objectives: tuple[str, ...]
    allowed_history_intents: frozenset[str]
    allowed_clinical_hypotheses: frozenset[str]
    observations: Mapping[str, ObservationDefinition]
    interventions: Mapping[str, InterventionDefinition]
    escalations: Mapping[str, EscalationDefinition]
    telemetry_keys: tuple[str, ...]
    completion_success_rules: tuple[str, ...]
    completion_failure_rules: tuple[str, ...]
    mode: str = "learning"
    schema_version: str = "1.2"

    def validate(self) -> None:
        if self.schema_version != "1.2":
            raise ValueError("Unsupported scenario schema version")
        if self.mode != "learning":
            raise ValueError("S0 supports learning mode only")
        if self.patient_template != "adult_male_standard":
            raise ValueError("S0 only supports the pinned adult standard template")
        if self.hemorrhage_compartment != "Spleen":
            raise ValueError("S0 pathology must be the existing splenic hemorrhage")
        if self.hemorrhage_flow_rate_ml_min <= 0:
            raise ValueError("Existing hemorrhage flow rate must be positive")
        if not self.learning_objectives:
            raise ValueError("Scenario requires learning objectives")
        if not self.allowed_history_intents.issubset(ALLOWED_HISTORY_INTENTS):
            raise ValueError("Scenario contains an unknown history intent")
        if not self.allowed_clinical_hypotheses.issubset(ALLOWED_CLINICAL_HYPOTHESES):
            raise ValueError("Scenario contains an unknown clinical hypothesis")
        if not self.observations:
            raise ValueError("Scenario requires authored observations")
        for observation_id, definition in self.observations.items():
            if observation_id != definition.observation_id:
                raise ValueError("Observation definitions must use matching identifiers")
            if observation_id not in {"FAST", "CBC"}:
                raise ValueError("Scenario contains an unsupported observation")
            if definition.enabled and not definition.controlled_finding:
                raise ValueError("Enabled authored observations require a controlled finding")
        if self.completion_success_rules or self.completion_failure_rules:
            raise ValueError("S0 completion rules must remain empty in learning mode")
        if not self.interventions:
            raise ValueError("Scenario requires at least one constrained intervention")
        for definition in self.interventions.values():
            if definition.pulse_compound not in {"Saline", "PackedRBC"}:
                raise ValueError("S0 intervention maps to an unsupported Pulse compound")
            if definition.volume_ml <= 0 or definition.rate_ml_min <= 0:
                raise ValueError("Intervention volume and rate must be positive")
        if not self.escalations:
            raise ValueError("Scenario requires at least one structured escalation option")
        for escalation_id, definition in self.escalations.items():
            if not escalation_id or escalation_id != definition.escalation_id:
                raise ValueError("Escalation definitions must use non-empty matching identifiers")

    def allowed_observation_ids(self) -> frozenset[str]:
        authored = {observation_id for observation_id, definition in self.observations.items() if definition.enabled}
        return BUILT_IN_OBSERVATION_IDS | frozenset(authored)

    def clinical_hypothesis(self, hypothesis_id: str) -> str:
        if hypothesis_id not in self.allowed_clinical_hypotheses:
            raise ValueError(f"Clinical hypothesis not allowed by scenario: {hypothesis_id}")
        return hypothesis_id

    def intervention(self, intervention_id: str) -> InterventionDefinition:
        try:
            return self.interventions[intervention_id]
        except KeyError as exc:
            raise ValueError(f"Intervention not allowed by scenario: {intervention_id}") from exc

    def escalation(self, escalation_id: str) -> EscalationDefinition:
        try:
            return self.escalations[escalation_id]
        except KeyError as exc:
            raise ValueError(f"Escalation not allowed by scenario: {escalation_id}") from exc


def splenic_hemorrhage_learning_scenario() -> S0Scenario:
    scenario = S0Scenario(
        scenario_id="trauma_splenic_01",
        title="Abdominal trauma: active splenic hemorrhage",
        pulse_revision="e8a36497b8ba78e788dc201a6baf74e1c297c56f",
        patient_template="adult_male_standard",
        hemorrhage_compartment="Spleen",
        hemorrhage_flow_rate_ml_min=60.0,
        learning_objectives=(
            "identify_deterioration",
            "suspect_internal_bleeding",
            "request_fast",
            "begin_resuscitation",
            "reassess",
        ),
        allowed_history_intents=frozenset(
            {"PAIN_ONSET", "PAIN_LOCATION", "MECHANISM_OF_INJURY"}
        ),
        allowed_clinical_hypotheses=frozenset({"INTERNAL_BLEEDING"}),
        observations={
            "FAST": ObservationDefinition(
                observation_id="FAST",
                enabled=True,
                controlled_finding="free_fluid_positive",
            )
        },
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
        escalations={
            "trauma_team_escalation": EscalationDefinition(
                escalation_id="trauma_team_escalation"
            )
        },
        telemetry_keys=(
            "heart_rate_bpm",
            "mean_arterial_pressure_mmhg",
            "blood_volume_ml",
            "total_hemorrhaged_volume_ml",
            "oxygen_saturation",
        ),
        completion_success_rules=(),
        completion_failure_rules=(),
    )
    scenario.validate()
    return scenario
