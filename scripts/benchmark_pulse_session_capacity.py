#!/usr/bin/env python3
"""Measure one-host concurrent S0 VPE/Pulse capacity with real Pulse subprocesses.

This is a headless local engineering benchmark, not a production capacity claim,
clinical validation, Unity benchmark, network benchmark, or deployment sizing tool.
It reuses the existing VPE-owned clock and PulseAdapter process contract. Each session
owns one adapter process and is advanced by its VPE-paced host in a thread only for
benchmark concurrency; no learner/client path touches Pulse directly.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import math
import os
import platform
import shutil
import statistics
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import psutil

from nexora_vpe import (
    PulseAdapter,
    PulseAdapterConfig,
    VpeClientFacade,
    VpePacedHost,
    VpeRuntime,
    load_s0_scenario,
)
from nexora_vpe.model import CommandKind


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "trauma_splenic_01.json"
DEFAULT_SESSION_COUNTS = (1, 2, 4, 8, 16, 32)
SATURATION_CPU_PCT = 90.0
SATURATION_MIN_AVAILABLE_MEMORY_RATIO = 0.10
SATURATION_IO_BUSY_PCT = 90.0


@dataclass
class SessionRuntime:
    index: int
    adapter: PulseAdapter
    runtime: VpeRuntime
    host: VpePacedHost
    process: psutil.Process
    start_wall_ms: float


def percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile for no values")
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


def process_cpu_seconds(process: psutil.Process) -> float:
    try:
        times = process.cpu_times()
    except psutil.Error:
        return 0.0
    return float(times.user + times.system)


def process_rss_bytes(process: psutil.Process) -> int:
    try:
        return int(process.memory_info().rss)
    except psutil.Error:
        return 0


def system_busy_cpu_seconds() -> float:
    times = psutil.cpu_times()
    return float(
        sum(
            float(getattr(times, field, 0.0))
            for field in ("user", "nice", "system", "irq", "softirq", "steal")
        )
    )


def system_disk_snapshot() -> dict[str, int | None]:
    counters = psutil.disk_io_counters()
    if counters is None:
        return {"read_bytes": None, "write_bytes": None, "busy_time_ms": None}
    return {
        "read_bytes": int(counters.read_bytes),
        "write_bytes": int(counters.write_bytes),
        "busy_time_ms": int(getattr(counters, "busy_time", 0)),
    }


def delta_or_none(after: int | None, before: int | None) -> int | None:
    if after is None or before is None:
        return None
    return max(0, after - before)


def start_session(index: int, pulse_root: Path, state_root: Path, tick_s: float) -> SessionRuntime:
    scenario = load_s0_scenario(SCENARIO_PATH)
    state_directory = state_root / f"session-{index:03d}"
    started = time.perf_counter_ns()
    adapter = make_adapter(pulse_root, state_directory)
    try:
        runtime = VpeRuntime(scenario=scenario, adapter=adapter)
        runtime.start()
        facade = VpeClientFacade(runtime)
        host = VpePacedHost(runtime, facade, tick_simulation_s=tick_s, sleep=lambda _: None)
        process = getattr(adapter, "_process", None)
        if process is None or process.pid is None:
            raise RuntimeError("PulseAdapter did not expose a live benchmark subprocess")
        return SessionRuntime(
            index=index,
            adapter=adapter,
            runtime=runtime,
            host=host,
            process=psutil.Process(process.pid),
            start_wall_ms=(time.perf_counter_ns() - started) / 1_000_000,
        )
    except Exception:
        adapter.close()
        raise


def close_session(session: SessionRuntime) -> dict[str, Any]:
    started = time.perf_counter_ns()
    try:
        session.adapter.close()
        return {"session_index": session.index, "shutdown_wall_ms": (time.perf_counter_ns() - started) / 1_000_000}
    except Exception as exc:  # pragma: no cover - benchmark records actual environment failures.
        return {
            "session_index": session.index,
            "shutdown_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "error": f"{type(exc).__name__}: {exc}",
        }


def tick_session(session: SessionRuntime) -> dict[str, Any]:
    before_cpu = process_cpu_seconds(session.process)
    before_time = session.runtime.simulation_time_s
    started = time.perf_counter_ns()
    try:
        result = session.host.tick_once()
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        return {
            "session_index": session.index,
            "tick_wall_ms": elapsed_ms,
            "tick_process_cpu_ms": (process_cpu_seconds(session.process) - before_cpu) * 1000,
            "overrun_s": float(result.overrun_s),
            "simulation_time_delta_s": session.runtime.simulation_time_s - before_time,
        }
    except Exception as exc:  # pragma: no cover - benchmark records actual environment failures.
        return {
            "session_index": session.index,
            "tick_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "tick_process_cpu_ms": (process_cpu_seconds(session.process) - before_cpu) * 1000,
            "error": f"{type(exc).__name__}: {exc}",
        }


def checkpoint_save(session: SessionRuntime, checkpoint_id: str) -> dict[str, Any]:
    started = time.perf_counter_ns()
    try:
        session.runtime.submit(CommandKind.CREATE_CHECKPOINT, "learner", {"checkpoint_id": checkpoint_id})
        session.runtime.drain()
        artifact = session.runtime.checkpoint_artifacts()[-1]
        state_path = Path(str(artifact.engine_state["state_path"]))
        return {
            "session_index": session.index,
            "checkpoint_save_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "checkpoint_size_bytes": state_path.stat().st_size,
            "checkpoint_id": checkpoint_id,
        }
    except Exception as exc:  # pragma: no cover - benchmark records actual environment failures.
        return {
            "session_index": session.index,
            "checkpoint_save_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "checkpoint_id": checkpoint_id,
            "error": f"{type(exc).__name__}: {exc}",
        }


def checkpoint_restore(session: SessionRuntime, checkpoint_id: str) -> dict[str, Any]:
    started = time.perf_counter_ns()
    try:
        session.runtime.submit(CommandKind.RESTORE_CHECKPOINT, "learner", {"checkpoint_id": checkpoint_id})
        session.runtime.drain()
        return {
            "session_index": session.index,
            "checkpoint_restore_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "checkpoint_id": checkpoint_id,
        }
    except Exception as exc:  # pragma: no cover - benchmark records actual environment failures.
        return {
            "session_index": session.index,
            "checkpoint_restore_wall_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "checkpoint_id": checkpoint_id,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_parallel(sessions: list[SessionRuntime], operation: Callable[[SessionRuntime], dict[str, Any]]) -> list[dict[str, Any]]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sessions)) as executor:
        return list(executor.map(operation, sessions))


def record_process_samples(
    rows: list[dict[str, Any]],
    sessions: list[SessionRuntime],
    session_count: int,
    trial: int,
    stage: str,
    tick_index: int | None,
) -> None:
    for session in sessions:
        rows.append(
            {
                "session_count": session_count,
                "trial": trial,
                "stage": stage,
                "tick_index": "" if tick_index is None else tick_index,
                "session_index": session.index,
                "pid": session.process.pid,
                "rss_bytes": process_rss_bytes(session.process),
                "process_cpu_seconds": process_cpu_seconds(session.process),
            }
        )


def run_level(
    pulse_root: Path,
    session_count: int,
    trial: int,
    tick_s: float,
    warmup_ticks: int,
    measure_ticks: int,
    process_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    tick_rows: list[dict[str, Any]] = []
    start_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    shutdown_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix=f"nexora-capacity-n{session_count}-t{trial}-") as directory:
        state_root = Path(directory)
        started = time.perf_counter_ns()
        sessions: list[SessionRuntime] = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=session_count) as executor:
                futures = [executor.submit(start_session, index, pulse_root, state_root, tick_s) for index in range(1, session_count + 1)]
                for index, future in enumerate(futures, start=1):
                    try:
                        session = future.result()
                        sessions.append(session)
                        start_rows.append(
                            {
                                "session_count": session_count,
                                "trial": trial,
                                "session_index": session.index,
                                "pid": session.process.pid,
                                "start_wall_ms": session.start_wall_ms,
                                "batch_start_wall_ms": "",
                            }
                        )
                    except Exception as exc:
                        failures.append(f"start session {index}: {type(exc).__name__}: {exc}")
            batch_start_ms = (time.perf_counter_ns() - started) / 1_000_000
            for row in start_rows:
                if row["session_count"] == session_count and row["trial"] == trial:
                    row["batch_start_wall_ms"] = batch_start_ms
            if len(sessions) != session_count:
                return tick_rows, start_rows, checkpoint_rows, shutdown_rows, [], failures

            record_process_samples(process_rows, sessions, session_count, trial, "post_boot", None)
            for _ in range(warmup_ticks):
                warmup = run_parallel(sessions, tick_session)
                failures.extend(str(row["error"]) for row in warmup if "error" in row)
                if failures:
                    return tick_rows, start_rows, checkpoint_rows, shutdown_rows, [], failures

            for tick_index in range(1, measure_ticks + 1):
                wall_started = time.perf_counter_ns()
                host_cpu_before = system_busy_cpu_seconds()
                disk_before = system_disk_snapshot()
                memory_before = psutil.virtual_memory()
                results = run_parallel(sessions, tick_session)
                elapsed_s = (time.perf_counter_ns() - wall_started) / 1_000_000_000
                host_cpu_delta = max(0.0, system_busy_cpu_seconds() - host_cpu_before)
                disk_after = system_disk_snapshot()
                memory_after = psutil.virtual_memory()
                host_cpu_pct = 100.0 * host_cpu_delta / max(1e-9, elapsed_s * max(1, psutil.cpu_count(logical=True) or 1))
                disk_busy_ms = delta_or_none(disk_after["busy_time_ms"], disk_before["busy_time_ms"])
                disk_busy_pct = None if disk_busy_ms is None else 100.0 * disk_busy_ms / max(1e-9, elapsed_s * 1000)
                for result in results:
                    result.update(
                        {
                            "session_count": session_count,
                            "trial": trial,
                            "tick_index": tick_index,
                            "batch_tick_wall_ms": elapsed_s * 1000,
                            "host_cpu_util_pct": host_cpu_pct,
                            "host_available_memory_bytes": int(memory_after.available),
                            "host_memory_available_delta_bytes": int(memory_after.available - memory_before.available),
                            "disk_read_bytes_delta": delta_or_none(disk_after["read_bytes"], disk_before["read_bytes"]),
                            "disk_write_bytes_delta": delta_or_none(disk_after["write_bytes"], disk_before["write_bytes"]),
                            "disk_busy_pct": disk_busy_pct,
                        }
                    )
                tick_rows.extend(results)
                record_process_samples(process_rows, sessions, session_count, trial, "tick", tick_index)
                failures.extend(str(row["error"]) for row in results if "error" in row)
                if failures:
                    return tick_rows, start_rows, checkpoint_rows, shutdown_rows, [], failures

            record_process_samples(process_rows, sessions, session_count, trial, "pre_checkpoint", None)
            checkpoint_id_by_session = {session.index: f"capacity-n{session_count}-t{trial}-s{session.index}" for session in sessions}
            save_rows = run_parallel(sessions, lambda session: checkpoint_save(session, checkpoint_id_by_session[session.index]))
            for row in save_rows:
                row.update({"session_count": session_count, "trial": trial, "operation": "save"})
            checkpoint_rows.extend(save_rows)
            failures.extend(str(row["error"]) for row in save_rows if "error" in row)
            if failures:
                return tick_rows, start_rows, checkpoint_rows, shutdown_rows, [], failures
            record_process_samples(process_rows, sessions, session_count, trial, "post_checkpoint_save", None)

            restore_rows = run_parallel(sessions, lambda session: checkpoint_restore(session, checkpoint_id_by_session[session.index]))
            for row in restore_rows:
                row.update({"session_count": session_count, "trial": trial, "operation": "restore"})
            checkpoint_rows.extend(restore_rows)
            failures.extend(str(row["error"]) for row in restore_rows if "error" in row)
            record_process_samples(process_rows, sessions, session_count, trial, "post_checkpoint_restore", None)
            return tick_rows, start_rows, checkpoint_rows, shutdown_rows, [], failures
        finally:
            if sessions:
                closed = run_parallel(sessions, close_session)
                for row in closed:
                    row.update({"session_count": session_count, "trial": trial})
                shutdown_rows.extend(closed)
                failures.extend(str(row["error"]) for row in closed if "error" in row)


def numeric(rows: Iterable[dict[str, Any]], field: str) -> list[float]:
    return [float(row[field]) for row in rows if field in row and row[field] not in ("", None)]


def summarize_level(
    session_count: int,
    tick_rows: list[dict[str, Any]],
    process_rows: list[dict[str, Any]],
    start_rows: list[dict[str, Any]],
    checkpoint_rows: list[dict[str, Any]],
    shutdown_rows: list[dict[str, Any]],
    failures: list[str],
) -> dict[str, Any]:
    relevant_ticks = [row for row in tick_rows if row["session_count"] == session_count and "error" not in row]
    relevant_process = [row for row in process_rows if row["session_count"] == session_count]
    relevant_start = [row for row in start_rows if row["session_count"] == session_count]
    relevant_checkpoint = [row for row in checkpoint_rows if row["session_count"] == session_count and "error" not in row]
    relevant_shutdown = [row for row in shutdown_rows if row["session_count"] == session_count and "error" not in row]
    tick_wall = numeric(relevant_ticks, "tick_wall_ms")
    tick_overrun = numeric(relevant_ticks, "overrun_s")
    rss = numeric(relevant_process, "rss_bytes")
    tick_cpu = numeric(relevant_ticks, "host_cpu_util_pct")
    memory_available = numeric(relevant_ticks, "host_available_memory_bytes")
    disk_busy = numeric(relevant_ticks, "disk_busy_pct")
    start_wall = numeric(relevant_start, "start_wall_ms")
    shutdown_wall = numeric(relevant_shutdown, "shutdown_wall_ms")
    save_wall = numeric([row for row in relevant_checkpoint if row.get("operation") == "save"], "checkpoint_save_wall_ms")
    restore_wall = numeric([row for row in relevant_checkpoint if row.get("operation") == "restore"], "checkpoint_restore_wall_ms")
    checkpoint_sizes = numeric([row for row in relevant_checkpoint if row.get("operation") == "save"], "checkpoint_size_bytes")
    batch_start = numeric(relevant_start, "batch_start_wall_ms")
    total_rss_by_sample: dict[tuple[int, str, str], int] = {}
    for row in relevant_process:
        key = (int(row["trial"]), str(row["stage"]), str(row["tick_index"]))
        total_rss_by_sample[key] = total_rss_by_sample.get(key, 0) + int(row["rss_bytes"])
    aggregate_rss = list(total_rss_by_sample.values())
    hardware_memory = psutil.virtual_memory().total
    saturation_reasons: list[str] = []
    resource_pressure: list[str] = []
    if failures:
        saturation_reasons.append("session failure")
    if any(value > 0.0 for value in tick_overrun):
        saturation_reasons.append("tick overrun")
    if tick_cpu and max(tick_cpu) >= SATURATION_CPU_PCT:
        resource_pressure.append(f"host CPU >= {SATURATION_CPU_PCT:.0f}%")
    if memory_available and min(memory_available) < hardware_memory * SATURATION_MIN_AVAILABLE_MEMORY_RATIO:
        resource_pressure.append(f"available memory < {SATURATION_MIN_AVAILABLE_MEMORY_RATIO:.0%} of total")
    if disk_busy and max(disk_busy) >= SATURATION_IO_BUSY_PCT:
        resource_pressure.append(f"disk busy >= {SATURATION_IO_BUSY_PCT:.0f}%")

    def distribution(values: list[float], prefix: str) -> dict[str, float | None]:
        if not values:
            return {f"{prefix}_p50": None, f"{prefix}_p95": None, f"{prefix}_p99": None, f"{prefix}_max": None}
        return {
            f"{prefix}_p50": percentile(values, 0.50),
            f"{prefix}_p95": percentile(values, 0.95),
            f"{prefix}_p99": percentile(values, 0.99),
            f"{prefix}_max": max(values),
        }

    summary: dict[str, Any] = {
        "session_count": session_count,
        "tick_samples": len(tick_wall),
        "failed_operations": len(failures),
        "failure_examples": failures[:5],
        "saturation_observed": bool(saturation_reasons),
        "saturation_reason": "; ".join(saturation_reasons) if saturation_reasons else "not observed through this level",
        "resource_pressure": "; ".join(resource_pressure) if resource_pressure else "not observed through this level",
        "max_overrun_s": max(tick_overrun) if tick_overrun else None,
        "min_available_memory_bytes": min(memory_available) if memory_available else None,
        "max_host_cpu_util_pct": max(tick_cpu) if tick_cpu else None,
        "max_disk_busy_pct": max(disk_busy) if disk_busy else None,
        "aggregate_rss_max_bytes": max(aggregate_rss) if aggregate_rss else None,
        "aggregate_rss_p95_bytes": percentile([float(value) for value in aggregate_rss], 0.95) if aggregate_rss else None,
    }
    for values, prefix in (
        (tick_wall, "tick_wall_ms"),
        (rss, "pulse_process_rss_bytes"),
        (start_wall, "session_start_wall_ms"),
        (batch_start, "batch_start_wall_ms"),
        (shutdown_wall, "session_shutdown_wall_ms"),
        (save_wall, "checkpoint_save_wall_ms"),
        (restore_wall, "checkpoint_restore_wall_ms"),
        (checkpoint_sizes, "checkpoint_size_bytes"),
        (tick_cpu, "host_cpu_util_pct"),
        (disk_busy, "disk_busy_pct"),
        ([float(value) for value in aggregate_rss], "aggregate_rss_bytes"),
    ):
        summary.update(distribution(values, prefix))
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_session_counts(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values or any(value < 1 for value in values) or tuple(sorted(set(values))) != values:
        raise ValueError("--session-counts must be increasing, unique positive integers")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--session-counts", default=",".join(str(value) for value in DEFAULT_SESSION_COUNTS))
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--warmup-ticks", type=int, default=2)
    parser.add_argument("--measure-ticks", type=int, default=10)
    parser.add_argument("--tick-s", type=float, default=0.5)
    parser.add_argument("--continue-after-saturation", action="store_true")
    args = parser.parse_args()
    if args.trials < 1 or args.warmup_ticks < 0 or args.measure_ticks < 1 or not math.isfinite(args.tick_s) or args.tick_s <= 0:
        raise ValueError("invalid trials/tick parameters")
    session_counts = parse_session_counts(args.session_counts)
    pulse_root = args.pulse_root.resolve()
    if not (pulse_root / "bin" / "states" / "StandardMale@0s.json").is_file():
        raise FileNotFoundError("Pinned Pulse initial state was not found under --pulse-root")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tick_rows: list[dict[str, Any]] = []
    process_rows: list[dict[str, Any]] = []
    start_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    shutdown_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    all_failures: dict[int, list[str]] = {}
    for session_count in session_counts:
        level_failures: list[str] = []
        for trial in range(1, args.trials + 1):
            tick, starts, checkpoints, shutdowns, _, failures = run_level(
                pulse_root, session_count, trial, args.tick_s, args.warmup_ticks, args.measure_ticks, process_rows
            )
            tick_rows.extend(tick)
            start_rows.extend(starts)
            checkpoint_rows.extend(checkpoints)
            shutdown_rows.extend(shutdowns)
            level_failures.extend(failures)
            if failures:
                break
        all_failures[session_count] = level_failures
        summary = summarize_level(
            session_count, tick_rows, process_rows, start_rows, checkpoint_rows, shutdown_rows, level_failures
        )
        summaries.append(summary)
        print(json.dumps(summary, sort_keys=True))
        if summary["saturation_observed"] and not args.continue_after_saturation:
            break

    write_csv(args.output_dir / "tick_samples.csv", tick_rows)
    write_csv(args.output_dir / "process_samples.csv", process_rows)
    write_csv(args.output_dir / "session_start_samples.csv", start_rows)
    write_csv(args.output_dir / "checkpoint_samples.csv", checkpoint_rows)
    write_csv(args.output_dir / "session_shutdown_samples.csv", shutdown_rows)
    write_csv(args.output_dir / "capacity_summary.csv", summaries)
    metadata = {
        "benchmark": "pulse_vpe_one_host_concurrent_capacity_v0.1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": "trauma_splenic_01",
        "pulse_root": str(pulse_root),
        "pulse_adapter_server": os.environ.get(
            "PULSE_ADAPTER_SERVER", str(PROJECT_ROOT / ".build" / "pulse_bridge" / "nexora_pulse_adapter_server")
        ),
        "session_counts_requested": list(session_counts),
        "trials": args.trials,
        "warmup_ticks": args.warmup_ticks,
        "measure_ticks": args.measure_ticks,
        "tick_simulation_s": args.tick_s,
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "memory_total_bytes": psutil.virtual_memory().total,
            "psutil_version": psutil.__version__,
        },
        "saturation_policy": {
            "stop_on_first_saturation": not args.continue_after_saturation,
            "signals": {
                "operation_failure": True,
                "tick_overrun_s_gt_zero": True,
                "hard_saturation": ["operation_failure", "tick_overrun_s_gt_zero"],
                "resource_pressure_only": {
                    "host_cpu_util_pct_gte": SATURATION_CPU_PCT,
                    "available_memory_ratio_lt": SATURATION_MIN_AVAILABLE_MEMORY_RATIO,
                    "disk_busy_pct_gte": SATURATION_IO_BUSY_PCT,
                },
            },
        },
        "levels": summaries,
        "limitations": [
            "Headless local engineering evidence only; no Unity rendering, network, public transport, broker, cloud, or clinical validation.",
            "RSS is per-process resident-set size; summed RSS can double-count shared mapped pages and is not unique physical-memory accounting.",
            "The benchmark uses the existing VPE-owned 0.5-second host tick and one PulseAdapter subprocess per session; it does not benchmark a future worker supervisor.",
            "Saturation is observed only by the declared signals on this host and does not establish a portable host density or a 50,000-session claim.",
        ],
        "artifact_files": [
            "tick_samples.csv",
            "process_samples.csv",
            "session_start_samples.csv",
            "checkpoint_samples.csv",
            "session_shutdown_samples.csv",
            "capacity_summary.csv",
        ],
        "failures_by_level": all_failures,
    }
    (args.output_dir / "capacity_summary.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote capacity artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
