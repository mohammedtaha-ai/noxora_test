"""Pure comparison core for pinned canonical-replay reproducibility runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import Snapshot


@dataclass(frozen=True)
class TrajectoryComparison:
    """Comparison result for a baseline plus repeat recorded trajectories."""

    comparable: bool
    reason: str | None
    channels: dict[str, dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return {"comparable": self.comparable, "reason": self.reason, "channels": self.channels}


def compare_snapshot_trajectories(
    trajectories: Sequence[Sequence[Snapshot]],
    tolerance: float,
) -> TrajectoryComparison:
    """Compare append-ordered snapshot trajectories without claiming determinism."""

    if not trajectories:
        raise ValueError("At least one trajectory is required")
    if tolerance < 0:
        raise ValueError("Tolerance must be non-negative")
    baseline = trajectories[0]
    if any(len(trajectory) != len(baseline) for trajectory in trajectories[1:]):
        return TrajectoryComparison(False, "snapshot_count_mismatch", {})
    channels = tuple(baseline[0].telemetry) if baseline else ()
    comparable = True
    for snapshot_index, baseline_snapshot in enumerate(baseline):
        if any(
            trajectory[snapshot_index].reason != baseline_snapshot.reason
            or trajectory[snapshot_index].simulation_time_s != baseline_snapshot.simulation_time_s
            or set(trajectory[snapshot_index].telemetry) != set(baseline_snapshot.telemetry)
            for trajectory in trajectories[1:]
        ):
            comparable = False
    results: dict[str, dict[str, object]] = {}
    for channel in channels:
        deltas = [
            abs(float(snapshot.telemetry[channel]) - float(baseline[snapshot_index].telemetry[channel]))
            for trajectory in trajectories[1:]
            for snapshot_index, snapshot in enumerate(trajectory)
        ]
        maximum = max(deltas, default=0.0)
        results[channel] = {
            "max_abs_divergence": maximum,
            "within_tolerance": maximum <= tolerance,
            "comparisons": len(deltas),
        }
    return TrajectoryComparison(
        comparable=comparable,
        reason=None if comparable else "snapshot_shape_or_axis_mismatch",
        channels=results,
    )


def comparison_within_tolerance(comparison: TrajectoryComparison) -> bool:
    """Return the narrow observed condition used by the local harness conclusion."""

    return comparison.comparable and all(
        bool(channel["within_tolerance"]) for channel in comparison.channels.values()
    )
