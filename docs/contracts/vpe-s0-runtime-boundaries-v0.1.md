# VPE S0 Runtime Boundaries and Deferred Gaps

**Status:** Pre-Go hardening record.  
**Date:** 2026-08-26.  
**Scope:** Python VPE and the pinned Pulse bridge only; this document does not authorize a new clinical capability.

## Current S0 Boundary

The production adapter supports one scenario-authorized internal splenic hemorrhage configured during `BOOTSTRAP`, constrained `Saline` and `PackedRBC` interventions, owner-controlled time advancement, selected telemetry, and local save/restore state files.[1] Learner-facing HTTP reads consume VPE-owned cached state, snapshots, and events; they do not call the adapter or Pulse.[2]

| Area | Current contract | Status |
|---|---|---|
| Hemorrhage | A bootstrap-configured splenic hemorrhage is active for the S0 run. | Supported baseline only. |
| Learner intervention | Only bounded Saline and PackedRBC volume/rate requests pass the narrow adapter boundary. | Supported. |
| Hemorrhage stop/reduce/control | There is no learner, Control Plane, VPE, or Pulse bridge action to stop, reduce, redirect, or otherwise control the hemorrhage. | **Deferred gap; not implemented.** |
| Checkpoint restore | A saved adapter state may be restored after integrity and scenario/revision checks. | Supported as local state restore. |
| Branch replay | No branch identifier, parent branch identifier, parent checkpoint identifier, append-only branch event stream, or deterministic replay runner exists. | **Deferred gap; not implemented.** |

## Hemorrhage-Control Gap

The absence of hemorrhage-control is intentional in this batch. It must not be represented by sending arbitrary Pulse action strings, accepting a client-defined compartment or flow rate, or mutating a published scenario artifact in place. A future proposal must define a scenario-authorized runtime action, an explicit narrow bridge command, parameter limits, evidence/audit semantics, and S0-specific test evidence before it can be enabled. It also requires a separate scope decision; Pre-Go hardening neither adds nor simulates that action.

## Restore Is Not Branch Replay

A checkpoint restore rehydrates one verified local Pulse state inside a compatible scenario and engine revision. It does **not** create a branch, preserve a parent-child lineage, reproduce subsequent commands, or guarantee deterministic playback of a separate timeline. Calling it "replay" would overstate the current evidence and create an incorrect product contract.

Any future branch replay design must introduce durable branch lineage and immutable command/event ordering separately from checkpoint storage. Until then, product and platform documentation must use **checkpoint restore** rather than **branch replay**.

## References

[1] [PulseAdapter S0 action boundary](../../src/nexora_vpe/pulse_adapter.py).  
[2] [VPE runtime state ownership](../../src/nexora_vpe/runtime.py).
