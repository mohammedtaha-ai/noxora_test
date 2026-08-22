#!/usr/bin/env python3
"""Run the headless S0 orchestration demo with the deterministic test adapter.

This is an engineering demonstration of command ordering, events, and snapshots.
It is not a clinical simulation, decision-support tool, or treatment protocol.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexora_vpe import DeterministicPhysiologyAdapter, VpeRuntime, load_s0_scenario
from nexora_vpe.model import CommandKind


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "trauma_splenic_01.json"
OUTPUT = ROOT / "artifacts" / "representative-small-results" / "s0_runtime_demo.json"


def main() -> None:
    scenario = load_s0_scenario(SCENARIO)
    runtime = VpeRuntime(scenario=scenario, adapter=DeterministicPhysiologyAdapter())
    runtime.start()

    runtime.submit(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "MECHANISM_OF_INJURY"})
    runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "VITALS"})
    runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
    runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"})
    runtime.submit(CommandKind.APPLY_INTERVENTION, "learner", {"intervention_id": "crystalloid_saline"})
    runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 120.0})
    runtime.submit(CommandKind.CREATE_CHECKPOINT, "learner", {"checkpoint_id": "after_initial_resuscitation"})
    runtime.drain()

    runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
    runtime.drain()
    runtime.submit(CommandKind.RESTORE_CHECKPOINT, "learner", {"checkpoint_id": "after_initial_resuscitation"})
    runtime.submit(CommandKind.ADVANCE_TIME, "learner", {"duration_s": 60.0})
    runtime.drain()
    runtime.complete()

    payload = {
        "purpose": "Engineering-only S0 runtime demonstration; not medical advice or assessment.",
        "scenario_id": scenario.scenario_id,
        "runtime_state": runtime.state.value,
        "adapter_engine_version": runtime.adapter.engine_version,
        "event_count": len(runtime.events()),
        "snapshot_count": len(runtime.snapshots()),
        "events": [event.as_dict() for event in runtime.events()],
        "snapshots": [snapshot.as_dict() for snapshot in runtime.snapshots()],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"Events: {payload['event_count']}; snapshots: {payload['snapshot_count']}")


if __name__ == "__main__":
    main()
