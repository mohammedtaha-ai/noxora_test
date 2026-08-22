"""Scenario JSON loader for the versioned S0 authoring contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scenario import EscalationDefinition, InterventionDefinition, S0Scenario


def load_s0_scenario(path: str | Path) -> S0Scenario:
    source = Path(path)
    raw: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    try:
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
        scenario = S0Scenario(
            scenario_id=raw["id"],
            title=raw["title"],
            pulse_revision=raw["pulse_revision"],
            patient_template=raw["patient"]["template"],
            hemorrhage_compartment=pathology["compartment"],
            hemorrhage_flow_rate_ml_min=float(pathology["flow_rate_ml_min"]),
            allowed_history_intents=frozenset(raw["history"]["allowed_intents"]),
            interventions=interventions,
            escalations=escalations,
            telemetry_keys=tuple(raw["telemetry"]),
            mode=raw["mode"],
            schema_version=raw["schema_version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid S0 scenario contract: {source}") from exc
    scenario.validate()
    return scenario
