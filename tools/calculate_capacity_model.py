"""Calculate illustrative Nexora capacity-model scenarios.

Inputs are deliberately assumptions for architecture discussion, not measured
production traffic or a forecast.  The script emits a CSV used by the
architecture document.
"""

from __future__ import annotations

import csv
from pathlib import Path


LEARNER_COUNTS = (1_000, 100_000, 1_000_000)
CONCURRENT_SHARE = 0.05
CANONICAL_EVENTS_PER_ACTIVE_SESSION_PER_MINUTE = 8
TELEMETRY_SAMPLES_PER_ACTIVE_SESSION_PER_SECOND = 2
CANONICAL_EVENT_BYTES = 1_024
TELEMETRY_SAMPLE_BYTES = 200
DURABLE_CHECKPOINT_INTERVAL_MINUTES = 10
DURABLE_CHECKPOINT_BYTES = 2 * 1024 * 1024


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "artifacts" / "capacity_model" / "illustrative_capacity_model.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "registered_learners",
        "illustrative_active_sessions",
        "canonical_events_per_minute",
        "canonical_events_per_day",
        "canonical_event_gib_per_day",
        "telemetry_samples_per_second",
        "telemetry_samples_per_day",
        "telemetry_gib_per_day",
        "durable_checkpoints_per_minute",
        "checkpoint_gib_per_day",
    ]
    with output.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        for learners in LEARNER_COUNTS:
            active_sessions = learners * CONCURRENT_SHARE
            events_per_minute = active_sessions * CANONICAL_EVENTS_PER_ACTIVE_SESSION_PER_MINUTE
            telemetry_per_second = active_sessions * TELEMETRY_SAMPLES_PER_ACTIVE_SESSION_PER_SECOND
            checkpoints_per_minute = active_sessions / DURABLE_CHECKPOINT_INTERVAL_MINUTES
            writer.writerow(
                {
                    "registered_learners": learners,
                    "illustrative_active_sessions": int(active_sessions),
                    "canonical_events_per_minute": int(events_per_minute),
                    "canonical_events_per_day": int(events_per_minute * 60 * 24),
                    "canonical_event_gib_per_day": f"{events_per_minute * 60 * 24 * CANONICAL_EVENT_BYTES / 1024**3:.3f}",
                    "telemetry_samples_per_second": int(telemetry_per_second),
                    "telemetry_samples_per_day": int(telemetry_per_second * 60 * 60 * 24),
                    "telemetry_gib_per_day": f"{telemetry_per_second * 60 * 60 * 24 * TELEMETRY_SAMPLE_BYTES / 1024**3:.3f}",
                    "durable_checkpoints_per_minute": f"{checkpoints_per_minute:.0f}",
                    "checkpoint_gib_per_day": f"{checkpoints_per_minute * 60 * 24 * DURABLE_CHECKPOINT_BYTES / 1024**3:.3f}",
                }
            )
    print(output)


if __name__ == "__main__":
    main()
