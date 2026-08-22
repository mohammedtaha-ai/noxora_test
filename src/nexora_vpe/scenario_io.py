"""Scenario JSON loader for the versioned S0 authoring contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .scenario import (
    EscalationDefinition,
    InterventionDefinition,
    ObservationDefinition,
    S0Scenario,
)


_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "title",
        "mode",
        "pulse_revision",
        "patient",
        "pathology",
        "learning_objectives",
        "history",
        "clinical_hypotheses",
        "observations",
        "interventions",
        "escalations",
        "telemetry",
        "completion",
    }
)


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _list(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    return value


def _exact_keys(value: object, expected: frozenset[str], context: str) -> Mapping[str, Any]:
    mapping = _mapping(value, context)
    actual = frozenset(mapping)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise ValueError(f"{context} has unsupported or missing fields: missing={sorted(missing)} extra={sorted(extra)}")
    return mapping


def _unique_ids(items: list[Any], context: str) -> None:
    ids: list[str] = []
    for index, item in enumerate(items):
        mapping = _mapping(item, f"{context}[{index}]")
        identifier = mapping.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"{context}[{index}] requires a non-empty id")
        ids.append(identifier)
    if len(ids) != len(set(ids)):
        raise ValueError(f"{context} contains duplicate ids")


def _validate_raw_contract(raw: object) -> Mapping[str, Any]:
    scenario = _exact_keys(raw, _TOP_LEVEL_KEYS, "scenario")
    _exact_keys(scenario["patient"], frozenset({"template"}), "patient")
    pathology = _exact_keys(scenario["pathology"], frozenset({"existing_internal_hemorrhage"}), "pathology")
    _exact_keys(
        pathology["existing_internal_hemorrhage"],
        frozenset({"compartment", "flow_rate_ml_min"}),
        "pathology.existing_internal_hemorrhage",
    )
    _exact_keys(scenario["history"], frozenset({"allowed_intents"}), "history")
    _exact_keys(scenario["clinical_hypotheses"], frozenset({"allowed"}), "clinical_hypotheses")
    observations = _exact_keys(scenario["observations"], frozenset({"allowed"}), "observations")
    interventions = _exact_keys(scenario["interventions"], frozenset({"allowed"}), "interventions")
    escalations = _exact_keys(scenario["escalations"], frozenset({"allowed"}), "escalations")
    _exact_keys(scenario["completion"], frozenset({"success_rules", "failure_rules"}), "completion")

    observation_items = _list(observations["allowed"], "observations.allowed")
    intervention_items = _list(interventions["allowed"], "interventions.allowed")
    escalation_items = _list(escalations["allowed"], "escalations.allowed")
    for index, item in enumerate(observation_items):
        mapping = _mapping(item, f"observations.allowed[{index}]")
        allowed = frozenset({"id", "enabled", "controlled_finding"})
        extra = frozenset(mapping) - allowed
        required = frozenset({"id", "enabled"})
        if extra or required - frozenset(mapping):
            raise ValueError(f"observations.allowed[{index}] has unsupported or missing fields")
        if not isinstance(mapping["enabled"], bool):
            raise ValueError(f"observations.allowed[{index}].enabled must be boolean")
    for index, item in enumerate(intervention_items):
        _exact_keys(
            item,
            frozenset({"id", "pulse_compound", "volume_ml", "rate_ml_min"}),
            f"interventions.allowed[{index}]",
        )
    for index, item in enumerate(escalation_items):
        _exact_keys(item, frozenset({"id"}), f"escalations.allowed[{index}]")
    _unique_ids(observation_items, "observations.allowed")
    _unique_ids(intervention_items, "interventions.allowed")
    _unique_ids(escalation_items, "escalations.allowed")
    return scenario


def load_s0_scenario(path: str | Path) -> S0Scenario:
    source = Path(path)
    try:
        raw = _validate_raw_contract(json.loads(source.read_text(encoding="utf-8")))
        pathology = raw["pathology"]["existing_internal_hemorrhage"]
        interventions = {
            item["id"]: InterventionDefinition(
                intervention_id=item["id"],
                pulse_compound=item["pulse_compound"],
                volume_ml=float(item["volume_ml"]),
                rate_ml_min=float(item["rate_ml_min"]),
            )
            for item in raw["interventions"]["allowed"]
        }
        escalations = {
            item["id"]: EscalationDefinition(escalation_id=item["id"])
            for item in raw["escalations"]["allowed"]
        }
        observations = {
            item["id"]: ObservationDefinition(
                observation_id=item["id"],
                enabled=item["enabled"],
                controlled_finding=item.get("controlled_finding"),
            )
            for item in raw["observations"]["allowed"]
        }
        completion = raw["completion"]
        scenario = S0Scenario(
            scenario_id=raw["id"],
            title=raw["title"],
            pulse_revision=raw["pulse_revision"],
            patient_template=raw["patient"]["template"],
            hemorrhage_compartment=pathology["compartment"],
            hemorrhage_flow_rate_ml_min=float(pathology["flow_rate_ml_min"]),
            learning_objectives=tuple(raw["learning_objectives"]),
            allowed_history_intents=frozenset(raw["history"]["allowed_intents"]),
            allowed_clinical_hypotheses=frozenset(raw["clinical_hypotheses"]["allowed"]),
            observations=observations,
            interventions=interventions,
            escalations=escalations,
            telemetry_keys=tuple(raw["telemetry"]),
            completion_success_rules=tuple(completion["success_rules"]),
            completion_failure_rules=tuple(completion["failure_rules"]),
            mode=raw["mode"],
            schema_version=raw["schema_version"],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid S0 scenario contract: {source}") from exc
    scenario.validate()
    return scenario
