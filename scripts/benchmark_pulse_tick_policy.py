#!/usr/bin/env python3
"""Measure real-Pulse S0 host ticks for the pre-Unity pacing policy.

Measurements are local engineering evidence.  They do not measure Unity frames,
network transport, medical behavior, or an SLA.  The host sleep is intentionally
disabled so the artifact measures active work and computes the paced-loop sleep
budget separately.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexora_vpe import (
    PulseAdapter,
    PulseAdapterConfig,
    VpeClientFacade,
    VpePacedHost,
    VpeRuntime,
    load_s0_scenario,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "trauma_splenic_01.json"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


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


def run_trial(pulse_root: Path, tick_s: float, ticks: int, trial: int) -> list[dict[str, Any]]:
    scenario = load_s0_scenario(SCENARIO_PATH)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nexora-tick-benchmark-") as directory:
        adapter = make_adapter(pulse_root, Path(directory))
        try:
            runtime = VpeRuntime(scenario=scenario, adapter=adapter)
            runtime.start()
            facade = VpeClientFacade(runtime)
            host = VpePacedHost(runtime, facade, tick_simulation_s=tick_s, sleep=lambda _: None)
            for tick_index in range(1, ticks + 1):
                before_time = runtime.simulation_time_s
                wall_started = time.perf_counter_ns()
                cpu_started = time.process_time_ns()
                result = host.tick_once()
                cpu_ms = (time.process_time_ns() - cpu_started) / 1_000_000
                active_ms = (time.perf_counter_ns() - wall_started) / 1_000_000
                projection_started = time.perf_counter_ns()
                snapshot = facade.current_snapshot()
                projection_ms = (time.perf_counter_ns() - projection_started) / 1_000_000
                if snapshot is None:
                    raise RuntimeError("Host tick did not publish a learner-visible snapshot")
                rows.append(
                    {
                        "trial": trial,
                        "tick_index": tick_index,
                        "tick_simulation_s": tick_s,
                        "active_wall_ms": active_ms,
                        "cpu_ms": cpu_ms,
                        "client_projection_ms": projection_ms,
                        "simulation_time_delta_s": runtime.simulation_time_s - before_time,
                        "overrun_s": result.overrun_s,
                        "sleep_budget_s": max(0.0, tick_s - result.wall_elapsed_s),
                    }
                )
        finally:
            adapter.close()
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tick_s in sorted({float(row["tick_simulation_s"]) for row in rows}):
        subset = [row for row in rows if float(row["tick_simulation_s"]) == tick_s]
        active = [float(row["active_wall_ms"]) for row in subset]
        cpu = [float(row["cpu_ms"]) for row in subset]
        projection = [float(row["client_projection_ms"]) for row in subset]
        overrun = [float(row["overrun_s"]) for row in subset]
        deltas = [float(row["simulation_time_delta_s"]) for row in subset]
        results.append(
            {
                "tick_simulation_s": tick_s,
                "samples": len(subset),
                "active_wall_ms_median": statistics.median(active),
                "active_wall_ms_p95": percentile(active, 0.95),
                "cpu_ms_median": statistics.median(cpu),
                "client_projection_ms_median": statistics.median(projection),
                "max_overrun_s": max(overrun),
                "simulation_time_delta_s": (
                    tick_s
                    if all(math.isclose(delta, tick_s, rel_tol=0.0, abs_tol=1e-9) for delta in deltas)
                    else "VARIES"
                ),
                "paced_sleep_budget_ms_median": statistics.median([float(row["sleep_budget_s"]) * 1000 for row in subset]),
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-root", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--ticks", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 1 or args.ticks < 1:
        raise ValueError("--trials and --ticks must be at least 1")
    pulse_root = args.pulse_root.resolve()
    if not (pulse_root / "bin" / "states" / "StandardMale@0s.json").is_file():
        raise FileNotFoundError("Pinned Pulse initial state was not found under --pulse-root")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        row
        for tick_s in (0.1, 0.25, 0.5, 1.0, 2.0)
        for trial in range(1, args.trials + 1)
        for row in run_trial(pulse_root, tick_s, args.ticks, trial)
    ]
    raw_path = args.output_dir / "pulse_tick_samples.csv"
    summary_path = args.output_dir / "pulse_tick_summary.json"
    fields = [
        "trial",
        "tick_index",
        "tick_simulation_s",
        "active_wall_ms",
        "cpu_ms",
        "client_projection_ms",
        "simulation_time_delta_s",
        "overrun_s",
        "sleep_budget_s",
    ]
    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary_path.write_text(
        json.dumps(
            {
                "measured_at_utc": datetime.now(timezone.utc).isoformat(),
                "scenario": "trauma_splenic_01",
                "pulse_root": str(pulse_root),
                "trials": args.trials,
                "ticks_per_trial": args.ticks,
                "tick_results": summarize(rows),
                "policy": {
                    "selected_tick_simulation_s": 0.5,
                    "reason": "the measured Pulse step matches the requested 0.5-second increment with a material 1x sleep budget; no catch-up on overrun",
                },
                "limitations": [
                    "Local sandbox headless engineering measurement only; no Unity frame, rendering, or network cost.",
                    "Host sleep is disabled during measurement; sleep_budget_s is the budget a 1x paced loop would use.",
                    "process_time is a local process CPU indicator, not a full system CPU profile.",
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
