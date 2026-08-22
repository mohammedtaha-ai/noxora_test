#!/usr/bin/env python3
"""Benchmark client-critical PulseAdapter operations on the pinned local SDK.

This is an engineering latency measurement on the local sandbox, not a clinical
performance claim and not a Unity-frame-time benchmark. It deliberately measures
only calls made after a ready adapter has bootstrapped the S0 scenario.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from nexora_vpe import PulseAdapter, PulseAdapterConfig, load_s0_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "trauma_splenic_01.json"
TELEMETRY_KEYS = (
    "heart_rate_bpm",
    "mean_arterial_pressure_mmhg",
    "blood_volume_ml",
    "total_hemorrhaged_volume_ml",
    "oxygen_saturation",
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def adapter_factory(pulse_root: Path, state_directory: Path) -> PulseAdapter:
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


def measure(operation: str, adapter: PulseAdapter, action: Callable[[], Any]) -> dict[str, Any]:
    before = adapter.simulation_time_s
    started = time.perf_counter_ns()
    result = action()
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    after = adapter.simulation_time_s
    return {
        "operation": operation,
        "latency_ms": elapsed_ms,
        "simulation_time_before_s": before,
        "simulation_time_after_s": after,
        "simulation_time_delta_s": after - before,
        "result": result,
    }


def run_trial(pulse_root: Path, trial: int) -> list[dict[str, Any]]:
    scenario = load_s0_scenario(SCENARIO_PATH)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nexora-pulse-benchmark-") as directory:
        state_directory = Path(directory)
        adapter = adapter_factory(pulse_root, state_directory)
        try:
            adapter.bootstrap(scenario)
            telemetry = measure("telemetry_read", adapter, lambda: adapter.telemetry(TELEMETRY_KEYS))
            telemetry["trial"] = trial
            telemetry["checkpoint_size_bytes"] = ""
            rows.append(telemetry)

            for seconds in (1.0, 10.0, 60.0, 120.0):
                operation = measure(
                    f"advance_{int(seconds)}s",
                    adapter,
                    lambda seconds=seconds: adapter.advance(seconds),
                )
                operation["trial"] = trial
                operation["checkpoint_size_bytes"] = ""
                rows.append(operation)

            saved = measure("checkpoint_save", adapter, adapter.save_state)
            state = saved.pop("result")
            state_path = Path(str(state["state_path"]))
            saved["trial"] = trial
            saved["checkpoint_size_bytes"] = state_path.stat().st_size
            rows.append(saved)

            adapter.advance(30.0)
            restored = measure("checkpoint_restore", adapter, lambda: adapter.restore_state(state))
            restored["trial"] = trial
            restored["checkpoint_size_bytes"] = state_path.stat().st_size
            rows.append(restored)
        finally:
            adapter.close()
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    operations = sorted({str(row["operation"]) for row in rows})
    summary: list[dict[str, Any]] = []
    for operation in operations:
        subset = [row for row in rows if row["operation"] == operation]
        latencies = [float(row["latency_ms"]) for row in subset]
        deltas = [float(row["simulation_time_delta_s"]) for row in subset]
        checkpoint_sizes = [int(row["checkpoint_size_bytes"]) for row in subset if row["checkpoint_size_bytes"] != ""]
        summary.append(
            {
                "operation": operation,
                "samples": len(subset),
                "latency_ms_min": min(latencies),
                "latency_ms_median": statistics.median(latencies),
                "latency_ms_p95": percentile(latencies, 0.95),
                "latency_ms_max": max(latencies),
                "latency_ms_mean": statistics.fmean(latencies),
                "latency_ms_stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                "simulation_time_delta_s": deltas[0] if len(set(deltas)) == 1 else "VARIES",
                "checkpoint_size_bytes": (
                    checkpoint_sizes[0]
                    if checkpoint_sizes and len(set(checkpoint_sizes)) == 1
                    else checkpoint_sizes or None
                ),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-root", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 1:
        raise ValueError("--trials must be at least 1")
    pulse_root = args.pulse_root.resolve()
    if not (pulse_root / "bin" / "states" / "StandardMale@0s.json").is_file():
        raise FileNotFoundError("Pinned Pulse initial state was not found under --pulse-root")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [row for trial in range(1, args.trials + 1) for row in run_trial(pulse_root, trial)]
    summary = summarize(rows)
    raw_path = args.output_dir / "pulse_client_operation_samples.csv"
    summary_path = args.output_dir / "pulse_client_operation_summary.json"
    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            lineterminator="\n",
            fieldnames=[
                "trial",
                "operation",
                "latency_ms",
                "simulation_time_before_s",
                "simulation_time_after_s",
                "simulation_time_delta_s",
                "checkpoint_size_bytes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})
    summary_path.write_text(
        json.dumps(
            {
                "measured_at_utc": datetime.now(timezone.utc).isoformat(),
                "scenario": "trauma_splenic_01",
                "pulse_root": str(pulse_root),
                "trials": args.trials,
                "operations": summary,
                "limitations": [
                    "Local sandbox engineering measurement only; not a production or Unity frame-time benchmark.",
                    "Bootstrap process creation and CMake build time are excluded.",
                    "A checkpoint restore follows an extra 30-second advance and therefore has a negative simulation-time delta.",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {raw_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
