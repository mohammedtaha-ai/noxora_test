# Nexora VPE — Proposed Decisions for v0.3

**Project:** `nexora-vpe`  
**Target baseline:** Nexora VPE Master Plan v0.3  
**Existing baseline:** `#906 — v0.2`  
**Purpose:** Review packet for manual creation in mxLore

---

# DEC-007 — S0 delivery cap and milestone consolidation

**Status:** Proposed → Active if approved  
**Suggested tags:** `decision`, `s0`, `schedule`, `scope`, `milestones`

## Decision

S0 must reach final S0 validation within a **20-week target** from implementation kickoff, with a **hard stop/re-scope review at 24 weeks**.

The separate v0.2 design milestones for:

- learning objectives + rubric,
- scenario schema + evidence requirements,
- event contract,

are merged into **one two-week Design Sprint**.

The sprint produces:

```text
Learning Objectives
→ Draft Rubric
→ Evidence Inventory
→ Interaction Inventory
→ Scenario Schema
→ Event Contract Draft
```

## Rationale

v0.2 reduced technical scope but still increased milestone fragmentation.

Separate design milestones create:

- extra handoffs,
- artificial completion points,
- schedule drift,
- architecture work with no independent user value.

The schedule cap is a scope-control mechanism.

If a feature does not fit, it is simplified, merged, or deferred.

## Consequences

- S0 is optimized for a complete validated vertical slice, not architectural completeness.
- Week 24 triggers an explicit:
  - STOP,
  - RE-SCOPE,
  - or architecture/product PIVOT review.
- No silent extension of S0.

## Suggested mx relations

```text
v0.3 implements DEC-007
DEC-007 references #906
```

---

# DEC-008 — Gates require explicit STOP criteria and Pulse capability matrix

**Status:** Proposed → Active if approved  
**Suggested tags:** `decision`, `gate-0`, `gate-a`, `pulse`, `stop-criteria`, `capability-matrix`

## Decision

Gate 0 and Gate A are **falsifiable gates**.

STOP/PIVOT criteria must be defined before execution.

Gate A must produce a binary/tri-state capability matrix for required Pulse functions.

## Gate 0 protocol

Directional discovery target:

- at least 5 clinical-phase learners,
- at least 3 clinicians / simulation educators.

This is not a statistical educational-efficacy study.

## Gate 0 STOP / PIVOT criteria

The current product hypothesis must be reworked if:

1. the majority of participants cannot describe a learning benefit beyond novelty;
2. fewer than 2 of 3 educators would be willing to trial the concept assuming acceptable clinical accuracy/content;
3. educator feedback indicates that dynamic physiological consequences are not a meaningful adoption driver;
4. instructor/content workflow needs dominate the value proposition and the current product direction does not address them.

## Gate A capability matrix

Each required item receives:

```text
SUPPORTED
PARTIAL
ABSENT
```

plus workaround estimate:

```text
≤2 days
3–5 days
>5 days
```

Minimum capability rows:

- internal/splenic hemorrhage,
- heart-rate output,
- BP/MAP output,
- blood volume/loss,
- required respiratory/oxygenation outputs,
- crystalloid,
- blood / PRBC,
- hemorrhage stop/control,
- serialize/save,
- load/restore.

Optional rows:

- TXA,
- vasopressor,
- later interventions.

## Gate A hard blockers for Pulse

Reject Pulse as the S0 physiology foundation if:

1. VPE cannot reliably own simulation-time advancement;
2. required hemorrhage progression or core outputs cannot be represented;
3. minimum resuscitation actions cannot be represented;
4. stable headless execution cannot be achieved;
5. required S0 behavior needs a workaround larger than the S0 spike budget;
6. clinical review finds the core trajectory unusable without changes large enough to defeat the reuse strategy.

Checkpoint/serialization absence is **not automatically fatal** to S0.

It may instead defer branch replay.

## Suggested mx relations

```text
v0.3 implements DEC-008
DEC-008 references #905
DEC-008 references #906
```

---

# DEC-009 — FAST is the only required spatial 3D interaction in S0

**Status:** Proposed → Active if approved  
**Suggested tags:** `decision`, `s0`, `3d`, `fast`, `anatomy-resolver`, `scope`

## Decision

S0 requires exactly one spatial 3D proof interaction:

> **FAST probe placement**

Other candidate interactions remain UI/menu interactions or are deferred.

Deferred as spatial systems:

- abdominal palpation,
- IV access targeting,
- patient positioning mechanics,
- anatomy exploration,
- generic procedural targeting,
- surgical tools.

## Architecture correction

Restore an explicit:

> **Anatomy Target Resolver**

to VPE Core.

In S0 its narrow responsibility is:

```text
Probe position/orientation
      ↓
Anatomical target
      ↓
Valid / invalid acquisition
      ↓
Observation Layer
      ↓
Structured evidence
```

## Gate D

Gate D proves one chain:

```text
FAST probe
→ Anatomy Target Resolver
→ Valid/invalid view
→ Scenario-dependent FAST observation
→ Structured event
```

## Rationale

One successful 3D-to-clinical-evidence chain proves the architecture.

Six spatial systems would reintroduce scope creep without proportionally increasing validation value.

## Suggested mx relations

```text
v0.3 implements DEC-009
DEC-009 references #900
DEC-009 references #906
```

---

# DEC-010 — S0 ships Learning Mode only; Assessment Mode moves to S1

**Status:** Proposed → Active if approved  
**Suggested tags:** `decision`, `s0`, `learning-mode`, `assessment`, `timing`, `regulatory`

## Decision

S0 ships **Learning Mode only**.

Assessment Mode is deferred to S1.

The VPE clock architecture remains unchanged, but S0 does not use high-stakes timing to determine:

- pass/fail,
- learner progression,
- consequential academic outcomes.

## S0 timing rules

- simulation time may run at 1× during clinical progression;
- system/UI pauses do not count;
- model/network latency does not count;
- Learning Mode may allow explicit pause/retry according to scenario policy.

Structured timing evidence can still be collected for formative debrief.

## Rationale

Assessment Mode introduces unnecessary S0 complexity:

- fairness around latency,
- system-interruption accounting,
- validation requirements,
- regulatory sensitivity,
- institutional-policy requirements.

These do not need to be solved before proving product value.

## Revisit trigger

Assessment Mode can return in S1 only after documenting:

- system-latency accounting,
- timing policy,
- validation approach,
- applicable regulatory obligations,
- intended institutional use.

## Suggested mx relations

```text
v0.3 implements DEC-010
DEC-010 references #901
DEC-010 references #903
DEC-010 references #906
```

---

# DEC-011 — S0 history-taking uses structured clinical intents

**Status:** Proposed → Active if approved  
**Suggested tags:** `decision`, `s0`, `history-taking`, `llm`, `interaction-inventory`, `structured-intents`

## Decision

The authoritative S0 history-taking model is:

> **Structured Clinical Intents**

It is neither:

- unrestricted free-text LLM conversation,
- nor a purely cosmetic fixed questionnaire.

## Example intent taxonomy

```text
PAIN_ONSET
PAIN_LOCATION
PAIN_RADIATION
PAIN_SEVERITY
ASSOCIATED_SYMPTOMS
MECHANISM_OF_INJURY
MEDICATIONS
ALLERGIES
PAST_MEDICAL_HISTORY
ANTICOAGULANT_USE
```

## Interaction model

Learner may:

1. select an intent directly, or
2. optionally use natural language.

If natural language is used:

```text
Learner wording
      ↓
Intent mapping
      ↓
Supported clinical intent
      ↓
Scenario fact
      ↓
Patient response
```

The structured intent is authoritative.

The optional language layer is not.

Low-confidence mapping must:

- ask for clarification,
- or fall back to structured options.

## AI patient

The AI Patient may phrase an answer only from allowed scenario facts.

It may not:

- invent new history,
- leak hidden diagnosis,
- alter state,
- create authoritative evidence.

## Timing and assessment

- model/network latency is system time;
- it does not count as clinical time;
- S0 debrief evaluates which clinical intents were elicited and their timing/sequence;
- it does not score the prose quality of the generated patient response.

## Interaction inventory requirement

The Design Sprint must classify every S0 interaction as:

```text
Structured UI
Optional natural-language layer
Spatial 3D
Deferred
```

## Rationale

This preserves a conversational product experience while keeping:

- truth,
- evidence,
- timing,
- replay,
- and assessment

structured and testable.

## Suggested mx relations

```text
v0.3 implements DEC-011
DEC-011 references #902
DEC-011 references #903
DEC-011 references #906
```

---

# Recommended mxLore update after approval

1. Create `DEC-007 → DEC-011` as `decision`, status `active`.
2. Create `Nexora VPE Master Plan v0.3 — Active Baseline` as `reference`, status `active`.
3. Add:

```text
v0.3 supersedes #906
v0.3 implements DEC-007
v0.3 implements DEC-008
v0.3 implements DEC-009
v0.3 implements DEC-010
v0.3 implements DEC-011
```

4. Preserve existing v0.3 inheritance from decisions `#900–#905` by adding:

```text
v0.3 implements #900
v0.3 implements #901
v0.3 implements #902
v0.3 implements #903
v0.3 implements #904
v0.3 implements #905
```

5. Mark `#906` as `superseded` or `archived` according to project convention.
6. Keep `#898` historical.

---

**End — Proposed v0.3 Decision Packet**
