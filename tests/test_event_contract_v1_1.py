from __future__ import annotations

import json
from pathlib import Path
import unittest

from nexora_vpe import DeterministicPhysiologyAdapter, VpeRuntime
from nexora_vpe.events import validate_event
from nexora_vpe.model import CommandKind, Event, EventContractStatus, EventType, SCHEMA_VERSION, event_contract_status
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class EventContractV11Tests(unittest.TestCase):
    def test_model_and_json_schema_freeze_the_same_v1_1_event_set(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas" / "event-envelope.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("1.1", SCHEMA_VERSION)
        self.assertEqual("1.1", schema["properties"]["schema_version"]["const"])
        self.assertEqual(
            {event_type.value for event_type in EventType},
            set(schema["properties"]["event_type"]["enum"]),
        )
        self.assertIn("fast.acquisition.recorded", schema["properties"]["event_type"]["enum"])
        self.assertIn("runtime.paused_by_system", schema["properties"]["event_type"]["enum"])
        fast_status = schema["x-nexora-event-type-status"]["fast.acquisition.recorded"]
        self.assertEqual("RESERVED", fast_status["status"])
        self.assertEqual("future_fast_resolver", fast_status["producer"])
        self.assertFalse(fast_status["current_production"])
        self.assertEqual(EventContractStatus.RESERVED, event_contract_status(EventType.FAST_ACQUISITION_RECORDED))
        self.assertEqual(EventContractStatus.ACTIVE, event_contract_status(EventType.RUNTIME_PAUSED_BY_SYSTEM))

    def test_reserved_fast_event_cannot_be_emitted_by_current_runtime_producers(self) -> None:
        runtime = VpeRuntime(splenic_hemorrhage_learning_scenario(), DeterministicPhysiologyAdapter())
        runtime.start()
        runtime.submit(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"})
        runtime.drain()
        self.assertNotIn(
            EventType.FAST_ACQUISITION_RECORDED,
            {event.event_type for event in runtime.events()},
        )

    def test_v1_0_event_is_rejected_without_silent_compatibility(self) -> None:
        old_event = Event(
            event_id="evt-old",
            scenario_id="trauma_splenic_01",
            simulation_time_s=0.0,
            event_type=EventType.CLOCK_ADVANCED,
            actor="runtime",
            payload={"command_id": "cmd-old", "duration_s": 0.5},
            source="vpe_core",
            schema_version="1.0",
        )
        with self.assertRaisesRegex(ValueError, "Unsupported event schema version"):
            validate_event(old_event)

    def test_system_pause_event_is_canonical_and_contains_no_engine_state(self) -> None:
        runtime = VpeRuntime(splenic_hemorrhage_learning_scenario(), DeterministicPhysiologyAdapter())
        runtime.start()
        runtime.pause_by_system("test_safety_pause")
        event = runtime.events()[-1]
        self.assertEqual(EventType.RUNTIME_PAUSED_BY_SYSTEM, event.event_type)
        self.assertEqual("system", event.actor)
        self.assertEqual("vpe_core", event.source)
        self.assertEqual({"reason": "test_safety_pause"}, dict(event.payload))
        self.assertEqual(SCHEMA_VERSION, event.schema_version)


if __name__ == "__main__":
    unittest.main()
