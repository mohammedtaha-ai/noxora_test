#!/usr/bin/env python3
"""Measure reproducibility of one pinned, headless VPE/Pulse command trajectory.

This is a local engineering harness. It does not provide a production SLO, a
clinical validation, a claim of determinism, or any server/client integration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from nexora_vpe import (
    PulseAdapter,
    PulseAdapterConfig,
    VpeRuntime,
    canonical_timeline,
    record_session,
    serialize_recorded_session,
    serialize_timeline,
)
from nexora_vpe.model import CommandKind, Snapshot
from nexora_vpe.regression import comparison_within_tolerance, compare_snapshot_trajectories
from nexora_vpe.scenario_io import load_s0_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "trauma_splenic_01.json"
DEFAULT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class CommandSpec:
    kind: CommandKind
    actor: str
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind.value, "actor": self.actor, "payload": dict(self.payload)}


PINNED_COMMANDS = (
    CommandSpec(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "PAIN_ONSET"}),
    CommandSpec(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "PAIN_LOCATION"}),
    CommandSpec(CommandKind.RECORD_HISTORY_INTENT, "learner", {"intent_id": "MECHANISM_OF_INJURY"}),
    CommandSpec(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "VITALS"}),
    CommandSpec(
        CommandKind.RECORD_CLINICAL_HYPOTHESIS,
        "learner",
        {"hypothesis_id": "INTERNAL_BLEEDING"},
    ),
    CommandSpec(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "FAST"}),
    CommandSpec(CommandKind.ADVANCE_TIME, "runtime", {"duration_s": 60.0}),
    CommandSpec(
        CommandKind.APPLY_INTERVENTION,
        "learner",
        {"intervention_id": "crystalloid_saline"},
    ),
    CommandSpec(CommandKind.ADVANCE_TIME, "runtime", {"duration_s": 60.0}),
    CommandSpec(CommandKind.REQUEST_OBSERVATION, "learner", {"observation_id": "VITALS"}),
    CommandSpec(
        CommandKind.RECORD_ESCALATION,
        "learner",
        {"escalation_id": "trauma_team_escalation"},
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_adapter(pulse_root: Path, state_directory: Path) -> PulseAdapter:
    server = Path(
        os.environ.get(
            "PULSE_ADAPTER_SERVER",
            str(PROJECT_ROOT / ".build" / "pulse_bridge" / "nexora_pulse_adapter_server"),
        )
    ).resolve()
    return PulseAdapter(
        PulseAdapterConfig(
            server_executable=server,
            pulse_working_directory=(pulse_root / "bin").resolve(),
            initial_state_file=(pulse_root / "bin" / "states" / "StandardMale@0s.json").resolve(),
            state_directory=state_directory,
            request_timeout_s=30.0,
        )
    )


def run_once(pulse_root: Path) -> tuple[dict[str, object], tuple[Snapshot, ...], str, str]:
    scenario = load_s0_scenario(SCENARIO_PATH)
    with tempfile.TemporaryDirectory(prefix="nexora-pulse-regression-") as directory:
        adapter = make_adapter(pulse_root, Path(directory))
        runtime = VpeRuntime(scenario, adapter)
        try:
            runtime.start()
            for command in PINNED_COMMANDS:
                runtime.submit(command.kind, command.actor, command.payload)
                runtime.drain()
            recording = record_session(runtime.events(), runtime.snapshots())
            timeline = canonical_timeline(recording)
            return (
                recording.as_dict(),
                runtime.snapshots(),
                serialize_recorded_session(recording),
                serialize_timeline(timeline),
            )
        finally:
            adapter.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pulse-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 5:
        raise SystemExit("--runs must be at least 5")
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        raise SystemExit("--tolerance must be a finite non-negative number")
    pulse_root = args.pulse_root.resolve()
    initial_state = pulse_root / "bin" / "states" / "StandardMale@0s.json"
    if not initial_state.is_file():
        raise SystemExit(f"Pulse initial state not found: {initial_state}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    recordings: list[dict[str, object]] = []
    trajectories: list[tuple[Snapshot, ...]] = []
    canonical_json: list[str] = []
    timeline_json: list[str] = []
    for _ in range(args.runs):
        recording, snapshots, serialized_recording, serialized_timeline = run_once(pulse_root)
        recordings.append(recording)
        trajectories.append(snapshots)
        canonical_json.append(serialized_recording)
        timeline_json.append(serialized_timeline)

    divergence = compare_snapshot_trajectories(trajectories, args.tolerance)
    byte_identical_recordings = len(set(canonical_json)) == 1
    byte_identical_timelines = len(set(timeline_json)) == 1
    within_tolerance = comparison_within_tolerance(divergence)
    scenario = load_s0_scenario(SCENARIO_PATH)
    summary = {
        "benchmark": "pulse_vpe_regression_replay_v0.1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Local one-host engineering evidence only; no Unity, network, broker, cloud, or clinical validation.",
            "This harness reports reproducibility for one pinned input set; it does not claim determinism across scenarios, hosts, operating systems, or Pulse revisions.",
        ],
        "inputs": {
            "pulse_root": str(pulse_root),
            "pulse_revision": scenario.pulse_revision,
            "scenario_path": str(SCENARIO_PATH),
            "scenario_sha256": sha256_file(SCENARIO_PATH),
            "initial_state_path": str(initial_state),
            "initial_state_sha256": sha256_file(initial_state),
            "commands": [command.as_dict() for command in PINNED_COMMANDS],
            "vpe_time_owner": True,
        },
        "runs": args.runs,
        "declared_tolerance": args.tolerance,
        "trajectory_comparison": divergence.as_dict(),
        "byte_identical_recorded_sessions": byte_identical_recordings,
        "byte_identical_timelines": byte_identical_timelines,
        "within_declared_tolerance": within_tolerance,
        "conclusion": "reproducible_within_declared_tolerance" if within_tolerance else "divergence_exceeds_tolerance_or_shape_mismatch",
    }
    (args.output_dir / "reproducibility_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "run_01.recorded_session.json").write_text(canonical_json[0] + "\n", encoding="utf-8")
    (args.output_dir / "run_01.timeline.json").write_text(timeline_json[0] + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if within_tolerance else 2


if __name__ == "__main__":
    raise SystemExit(main())
