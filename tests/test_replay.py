from __future__ import annotations

import json
import unittest

from nexora_vpe import (
    DeterministicPhysiologyAdapter,
    VpeRuntime,
    canonical_timeline,
    evaluate_evidence,
    evaluate_recording,
    record_session,
    recorded_session_from_dict,
    serialize_evaluation,
    serialize_recorded_session,
    serialize_timeline,
)
from nexora_vpe.model import CommandKind, EventType
from nexora_vpe.scenario import splenic_hemorrhage_learning_scenario


class CanonicalReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = VpeRuntime(splenic_hemorrhage_learning_scenario(), DeterministicPhysiologyAdapter())
        self.runtime.start()

    def _apply(self, kind: CommandKind, payload: dict[str, object]) -> None:
        self.runtime.submit(kind, "learner", payload)
        self.runtime.drain()

    def _recording_with_branch(self):  # type: ignore[no-untyped-def]
        self._apply(CommandKind.REQUEST_OBSERVATION, {"observation_id": "VITALS"})
        self._apply(CommandKind.ADVANCE_TIME, {"duration_s": 30.0})
        self._apply(CommandKind.CREATE_CHECKPOINT, {"checkpoint_id": "at_30"})
        self._apply(CommandKind.ADVANCE_TIME, {"duration_s": 30.0})
        self._apply(CommandKind.RESTORE_CHECKPOINT, {"checkpoint_id": "at_30"})
        self._apply(CommandKind.REQUEST_OBSERVATION, {"observation_id": "FAST"})
        return record_session(self.runtime.events(), self.runtime.snapshots())

    def test_timeline_is_append_ordered_but_uses_simulation_time_and_marks_branch(self) -> None:
        recording = self._recording_with_branch()
        timeline = canonical_timeline(recording)

        self.assertEqual("trauma_splenic_01", timeline.scenario_id)
        self.assertEqual("simulation_time_s", timeline.as_dict()["time_axis"])
        self.assertEqual(
            list(range(1, len(recording.events) + 1)),
            [entry.sequence for entry in timeline.entries],
        )
        restore_index = next(
            index
            for index, entry in enumerate(timeline.entries)
            if entry.event.event_type == EventType.CHECKPOINT_RESTORED
        )
        self.assertTrue(timeline.entries[restore_index].branch_boundary)
        self.assertEqual(0, timeline.entries[restore_index].branch_id)
        self.assertEqual(1, timeline.entries[restore_index + 1].branch_id)
        self.assertEqual(30.0, timeline.entries[restore_index].simulation_time_s)
        self.assertNotIn("wall", serialize_timeline(timeline).lower())

    def test_replayed_evaluator_finding_json_is_byte_identical_to_live_stream(self) -> None:
        recording = self._recording_with_branch()
        serialized = serialize_recorded_session(recording)
        replayed = recorded_session_from_dict(json.loads(serialized))

        live_result = evaluate_evidence(self.runtime.events(), self.runtime.snapshots())
        replay_result = evaluate_recording(replayed)
        self.assertEqual(serialize_evaluation(live_result), serialize_evaluation(replay_result))
        self.assertEqual(serialized, serialize_recorded_session(replayed))

    def test_recording_rejects_snapshot_reference_not_present_in_recorded_session(self) -> None:
        recording = self._recording_with_branch()
        payload = recording.as_dict()
        payload["snapshots"] = []
        replayed = recorded_session_from_dict(payload)
        with self.assertRaisesRegex(ValueError, "must reference a recorded snapshot"):
            canonical_timeline(replayed)


if __name__ == "__main__":
    unittest.main()
