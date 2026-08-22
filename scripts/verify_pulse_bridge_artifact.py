#!/usr/bin/env python3
"""Verify engineering invariants in the real Pulse SDK bridge artifact.

The verification checks only recorded simulator continuity. It does not assess
clinical appropriateness, diagnose, or recommend treatment.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "representative-small-results" / "pulse_sdk_bridge.json"


def main() -> None:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload["pulse_version"] != "4.3.2":
        raise SystemExit("Unexpected Pulse version in bridge artifact")
    if payload["pulse_hash"] != "e8a3649":
        raise SystemExit("Unexpected Pulse hash in bridge artifact")

    baseline = payload["baseline"]
    before = payload["before_snapshot"]
    original = payload["original_continued"]
    restored = payload["restored_continued"]
    if not before["total_hemorrhaged_volume_ml"] > baseline["total_hemorrhaged_volume_ml"]:
        raise SystemExit("Bridge did not record progressive hemorrhage before snapshot")
    if original != restored:
        raise SystemExit("Restored trajectory did not match original continuation exactly")
    if original["time_s"] != 180.0:
        raise SystemExit("Bridge continuation time is unexpected")

    print("PASS: Pulse bridge artifact has pinned provenance and exact continuation equality")


if __name__ == "__main__":
    main()
