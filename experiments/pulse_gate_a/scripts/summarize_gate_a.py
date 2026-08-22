#!/usr/bin/env python3
"""Summarize deterministic Pulse Gate A evidence CSVs.

This utility reports simulator telemetry only. It does not generate clinical
recommendations, treatment rules, diagnoses, or patient-specific conclusions.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "2026-08-22"
OUT_JSON = RESULTS / "summary.json"
OUT_MD = RESULTS / "summary.md"

METRICS = {
    "heart_rate_bpm": "HeartRate(1/min)",
    "map_mmhg": "MeanArterialPressure(mmHg)",
    "blood_volume_ml": "BloodVolume(mL)",
    "hemoglobin_content_g": "HemoglobinContent(g)",
    "hemorrhage_rate_ml_s": "TotalHemorrhageRate(mL/s)",
    "hemorrhaged_volume_ml": "TotalHemorrhagedVolume(mL)",
    "oxygen_saturation": "OxygenSaturation",
}

SCENARIOS = {
    "internal_spleen": {
        "file": "internal_spleen_observability.csv",
        "events_s": [0, 30, 31, 1260, 1261, 1660],
        "description": "Internal splenic hemorrhage, controlled stop, then observation.",
    },
    "saline": {
        "file": "hemorrhage_saline_observability.csv",
        "events_s": [0, 30, 620, 621, 740, 1040, 1140],
        "description": "Dual hemorrhage, controlled stop, then Saline compound infusion.",
    },
    "packed_rbc": {
        "file": "hemorrhage_packed_rbc_observability.csv",
        "events_s": [0, 30, 430, 431, 550, 2880],
        "description": "Dual hemorrhage, controlled stop, then PackedRBC compound infusion.",
    },
}


def as_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or "$" in cleaned:
        return None
    try:
        candidate = float(cleaned)
    except ValueError:
        return None
    return candidate if math.isfinite(candidate) else None


def load_rows(path: Path) -> list[dict[str, float | None]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {key: as_float(value) for key, value in raw.items()}
            if row.get("Time(s)") is not None:
                rows.append(row)
    if not rows:
        raise RuntimeError(f"No valid rows found in {path}")
    return rows


def row_at_time(rows: list[dict[str, float | None]], target: int) -> dict[str, float | None]:
    return min(rows, key=lambda row: abs((row["Time(s)"] or 0.0) - target))


def metric_snapshot(row: dict[str, float | None]) -> dict[str, float | None]:
    return {label: row.get(column) for label, column in METRICS.items()}


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def markdown_value(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def continuity_check() -> dict[str, object]:
    seed = load_rows(RESULTS / "snapshot_seed_continuation.csv")
    restored = load_rows(RESULTS / "snapshot_restore_continuation.csv")
    columns = [
        "TotalHemorrhageRate(mL/s)",
        "TotalHemorrhagedVolume(mL)",
        "HeartRate(1/min)",
        "MeanArterialPressure(mmHg)",
        "BloodVolume(mL)",
    ]
    seed_by_time = {row["Time(s)"]: row for row in seed}
    comparisons = []
    max_abs_difference = 0.0
    for restore_row in restored:
        time_s = restore_row["Time(s)"]
        seed_row = seed_by_time.get(time_s)
        if seed_row is None:
            continue
        differences = {}
        for column in columns:
            source = seed_row.get(column)
            restored_value = restore_row.get(column)
            if source is None or restored_value is None:
                differences[column] = None
                continue
            diff = abs(source - restored_value)
            max_abs_difference = max(max_abs_difference, diff)
            differences[column] = diff
        comparisons.append({"time_s": time_s, "absolute_differences": differences})
    return {
        "seed_csv": "snapshot_seed_continuation.csv",
        "restore_csv": "snapshot_restore_continuation.csv",
        "overlap_rows_compared": len(comparisons),
        "overlap_start_s": rounded(comparisons[0]["time_s"]) if comparisons else None,
        "overlap_end_s": rounded(comparisons[-1]["time_s"]) if comparisons else None,
        "max_absolute_difference": rounded(max_abs_difference),
        "exact_numeric_match": max_abs_difference == 0.0 and bool(comparisons),
    }


def main() -> None:
    summary: dict[str, object] = {
        "purpose": "Simulator evidence summary only; not clinical advice.",
        "result_directory": str(RESULTS.relative_to(ROOT)),
        "scenarios": {},
    }

    markdown_sections = [
        "# Pulse Gate A — CSV Evidence Summary",
        "",
        "> **Scope:** This is an engineering record of deterministic Pulse telemetry. It is not medical advice, a treatment protocol, a diagnosis, or a validated clinical model.",
        "",
        "All rows were generated locally from the pinned Pulse `stable` source build and are preserved with SHA-256 checksums in `SHA256SUMS.txt`.",
        "",
    ]

    for scenario_id, config in SCENARIOS.items():
        rows = load_rows(RESULTS / config["file"])
        by_event = {}
        for event_s in config["events_s"]:
            row = row_at_time(rows, event_s)
            by_event[str(event_s)] = {
                "observed_time_s": rounded(row["Time(s)"]),
                **{key: rounded(value) for key, value in metric_snapshot(row).items()},
            }

        bleed_values = [row.get(METRICS["hemorrhage_rate_ml_s"]) for row in rows]
        bleed_times = [row["Time(s)"] for row in rows if (row.get(METRICS["hemorrhage_rate_ml_s"]) or 0.0) > 0.0]
        rate_values = [value for value in bleed_values if value is not None]
        summary["scenarios"][scenario_id] = {
            "description": config["description"],
            "csv": config["file"],
            "rows": len(rows),
            "start_time_s": rounded(rows[0]["Time(s)"]),
            "end_time_s": rounded(rows[-1]["Time(s)"]),
            "positive_hemorrhage_start_s": rounded(min(bleed_times)) if bleed_times else None,
            "positive_hemorrhage_end_s": rounded(max(bleed_times)) if bleed_times else None,
            "max_hemorrhage_rate_ml_s": rounded(max(rate_values)) if rate_values else None,
            "event_snapshots": by_event,
        }

        markdown_sections.extend([
            f"## {scenario_id.replace('_', ' ').title()}",
            "",
            config["description"],
            "",
            f"The CSV contains **{len(rows)}** sampled rows from {rows[0]['Time(s)']:.0f}s to {rows[-1]['Time(s)']:.0f}s. Positive total hemorrhage telemetry begins at {min(bleed_times) if bleed_times else '—'}s and ends at {max(bleed_times) if bleed_times else '—'}s; the maximum recorded rate is {max(rate_values) if rate_values else '—'} mL/s.",
            "",
            "| Requested time (s) | Observed time (s) | HR (1/min) | MAP (mmHg) | Blood volume (mL) | Hemoglobin (g) | Hemorrhage rate (mL/s) | Total hemorrhage (mL) | SpO₂ |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for target_s, snapshot in by_event.items():
            markdown_sections.append(
                "| {target} | {observed} | {hr} | {map} | {blood} | {hgb} | {rate} | {total} | {spo2} |".format(
                    target=target_s,
                    observed=markdown_value(snapshot["observed_time_s"]),
                    hr=markdown_value(snapshot["heart_rate_bpm"]),
                    map=markdown_value(snapshot["map_mmhg"]),
                    blood=markdown_value(snapshot["blood_volume_ml"]),
                    hgb=markdown_value(snapshot["hemoglobin_content_g"]),
                    rate=markdown_value(snapshot["hemorrhage_rate_ml_s"]),
                    total=markdown_value(snapshot["hemorrhaged_volume_ml"]),
                    spo2=markdown_value(snapshot["oxygen_saturation"]),
                )
            )
        markdown_sections.append("")

    continuity = continuity_check()
    summary["snapshot_continuity"] = continuity
    markdown_sections.extend([
        "## Snapshot Continuity",
        "",
        "A state snapshot was saved at 150s during an active internal splenic hemorrhage, then reloaded into a second scenario which advanced for another 120s. The evidence comparison checks the overlapping simulator rows rather than inferring continuity from logs.",
        "",
        "| Compared overlapping rows | Overlap start (s) | Overlap end (s) | Maximum absolute numeric difference | Exact numeric match |",
        "| ---: | ---: | ---: | ---: | --- |",
        f"| {continuity['overlap_rows_compared']} | {markdown_value(continuity['overlap_start_s'])} | {markdown_value(continuity['overlap_end_s'])} | {markdown_value(continuity['max_absolute_difference'])} | {continuity['exact_numeric_match']} |",
        "",
    ])

    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text("\n".join(markdown_sections) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
