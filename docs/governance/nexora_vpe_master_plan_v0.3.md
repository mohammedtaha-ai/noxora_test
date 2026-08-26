# Nexora VPE — Master Plan v0.3

**Project slug:** `nexora-vpe`  
**Working name:** Nexora VPE — Virtual Patient Engine  
**Document role:** Proposed active architecture baseline  
**Supersedes:** `#906 — Nexora VPE Master Plan v0.2 — Active Baseline`  
**Historical predecessor:** `#898 — VPE Master Plan v0.1`  
**Already incorporated decisions:** `#900–#905`  
**Proposed new decisions:** `DEC-007 → DEC-011`  
**Status:** Proposed for review

---

# 0. Why v0.3 Exists

v0.3 is a scope-reduction release.

v0.2 fixed major architectural problems, but the plan still expanded into too many milestones and too many S0 interactions. v0.3 reduces the first release to the smallest complete experiment that can answer two questions:

1. **Does consequence-based virtual-patient training create enough educational value to justify a product?**
2. **Can Pulse support the minimum physiology needed for the first case without forcing us to build a physiology engine?**

Everything else is subordinate to those questions.

---

# 1. Product Vision

Build an interactive medical simulation platform where the learner manages a virtual patient whose state changes over time according to clinically meaningful rules.

The learner should eventually be able to:

- take history,
- examine the patient,
- request investigations,
- administer treatment,
- perform selected procedures,
- interact with 3D anatomy,
- make mistakes,
- observe physiological consequences,
- retry from meaningful checkpoints,
- receive evidence-based debrief,
- and receive increasingly targeted scenarios.

Long-term direction:

> **Digital Human Medical Simulator**

S0 direction:

> **One complete abdominal-trauma learning experience with credible consequences.**

---

# 2. Product Thesis

Nexora VPE is not primarily:

- an anatomy viewer,
- a medical chatbot,
- a scripted case player,
- a surgical simulator,
- or an LLM wrapper.

Its core product loop is:

```text
Learner Action
      ↓
Structured Clinical Meaning
      ↓
Simulation / Patient State
      ↓
Observable Consequence
      ↓
Structured Evidence
      ↓
Replay + Formative Debrief
```

The core architectural problem is:

```text
What did the learner do?
        ↓
What did that mean clinically?
        ↓
What happened to the patient?
        ↓
What evidence does that create about learning?
```

---

# 3. S0 Scope

## Domain

**Abdominal trauma**

## Reference case

**Splenic rupture with active internal hemorrhage progressing toward hemorrhagic shock**

The injury exists before the learner starts.

## S0 is

- clinical reasoning,
- recognition of deterioration,
- basic diagnostic sequencing,
- resuscitation,
- timing,
- observation,
- formative debrief.

## S0 is not

- surgery,
- tissue cutting,
- induced injury,
- suturing,
- haptics,
- patient-specific CT,
- whole-body anatomy,
- full trauma curriculum,
- high-stakes assessment.

---

# 4. S0 Interaction Inventory

Every S0 interaction belongs to one of four categories.

## A. Structured clinical interaction

Examples:

- history-taking intents,
- order CBC,
- order FAST,
- give crystalloid,
- give blood product,
- choose escalation.

These are authoritative structured actions.

## B. Optional natural-language UX

Natural language may map learner wording into a known structured clinical intent.

Example:

```text
"هل الألم ينتشر لمكان ثاني؟"
        ↓
PAIN_RADIATION
```

The free text itself is not authoritative.

## C. Spatial 3D interaction

**Exactly one required S0 spatial interaction: FAST probe placement.**

```text
Probe position/orientation
        ↓
Anatomy Target Resolver
        ↓
Valid / invalid acquisition
        ↓
Scenario-dependent FAST observation
        ↓
Structured evidence event
```

## D. Deferred

- 3D abdominal palpation system,
- spatial IV-access system,
- patient-positioning mechanics,
- free-form anatomy exploration,
- surgical tools,
- induced injuries,
- deformable tissue.

---

# 5. History-Taking Model

S0 history-taking uses **structured clinical intents**.

Example intent taxonomy:

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

The learner may interact through:

1. direct structured selection, or
2. optional natural-language input that maps to one supported intent.

Rules:

- low-confidence mapping falls back to clarification/structured choices;
- the LLM may phrase the patient's response;
- the LLM receives only allowed scenario facts;
- the structured intent is the evidence, not the generated sentence;
- model/network latency never counts as clinical time.

---

# 6. Authoritative Truth Model

```text
Anatomical Truth
      ↓
Pathological Truth
      ↓
Physiological Truth
      ↓
Observation Layer
      ↓
Learner-Available Evidence
      ↓
AI Expression
```

The LLM can express truth.

The LLM cannot redefine truth.

World state remains distinct from learner knowledge.

---

# 7. Simulation Clock

VPE owns simulation time.

```text
Wall Clock
≠
Simulation Clock
```

Runtime states:

```text
RUNNING
PAUSED_BY_SCENARIO
PAUSED_BY_SYSTEM
COMPLETED
```

## S0 Mode

**Learning Mode only.**

S0 may collect timing evidence for debrief, but timing does not determine high-stakes pass/fail or learner progression.

System latency, model latency, UI failure, and infrastructure pauses do not count as clinical time.

**Assessment Mode is deferred to S1.**

---

# 8. Replay Model

v0.3 keeps the three replay concepts from v0.2.

## Canonical replay

```text
Recorded events
+
Recorded state snapshots
```

Used for debrief, review, audit, and debugging.

## Checkpoint / branch replay

If Pulse serialization/load proves suitable:

```text
Saved physiology state
      ↓
Restore checkpoint
      ↓
Apply alternative action
      ↓
Create new future branch
```

This is conditional on Gate A.

## Regression replay

```text
Pinned engine version
+
Pinned config
+
Ordered commands
+
Controlled simulation time
      ↓
Compare trajectory within tolerance
```

The project uses **reproducibility**, not **determinism**, until stronger evidence exists.

---

# 9. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │  Scenario Director AI│
                         └──────────┬───────────┘
                                    │ validated schema
                                    ↓
┌───────────┐               ┌────────────────┐
│  Learner  │ ────────────→ │  Unity Client  │
└───────────┘               └───────┬────────┘
                                    │
                                    ↓
                         ┌──────────────────────┐
                         │       VPE Core       │
                         │                      │
                         │ Simulation Clock     │
                         │ Command Queue        │
                         │ Scenario Runtime     │
                         │ History Intent Map   │
                         │ Anatomy Target       │
                         │ Resolver             │
                         │ Observation Layer    │
                         │ Intervention Mapper  │
                         │ Evidence/Event Store │
                         └──────────┬───────────┘
                                    │
                             Physiology Adapter
                                    ↓
                         ┌──────────────────────┐
                         │        Pulse         │
                         └──────────┬───────────┘
                                    │
                              Patient State
                                    ↓
                  ┌─────────────────┼─────────────────┐
                  ↓                 ↓                 ↓
               Monitor        Unity / FAST       AI Patient
```

Pulse has a single runtime owner.

Unity and the LLM do not mutate Pulse independently.

---

# 10. Scenario Authoring

Scenario scalability is a first-class requirement.

Target model:

```text
Clinical Author
      ↓
Structured Scenario Definition
      ↓
Validation
      ↓
VPE Runtime
```

Conceptual schema:

```yaml
scenario:
  id: trauma_splenic_01
  domain: abdominal_trauma
  difficulty: learning

patient:
  template: adult_male

pathology:
  splenic_hemorrhage:
    severity: moderate

learning_objectives:
  - identify_deterioration
  - suspect_internal_bleeding
  - request_fast
  - begin_resuscitation
  - escalate_care

observations:
  cbc: enabled
  fast: enabled

interventions:
  - crystalloid
  - blood_product

completion:
  success_rules: []
  failure_rules: []
```

S0 does not require an authoring UI.

It does require a schema that does not assume every new scenario needs a programmer.

---

# 11. Assessment and Debrief

S0 assessment is **formative**.

Design order:

```text
Learning Objectives
      ↓
Draft Rubric
      ↓
Evidence Requirements
      ↓
Event Contract
```

Potential evidence dimensions:

- instability recognition,
- hemorrhage suspicion,
- diagnostic sequencing,
- FAST use,
- resuscitation timing,
- intervention appropriateness,
- reassessment,
- escalation.

Authoritative evidence comes from structured events and state trajectories.

The AI Instructor:

- explains,
- summarizes,
- connects cause and consequence,
- suggests retry points.

The AI Instructor does **not** own pass/fail.

---

# 12. Gate 0 — Value Discovery

Gate 0 runs in parallel with Gate A.

## Purpose

Test whether dynamic physiological consequences and replay/debrief create educational value beyond a conventional static case.

## Prototype

**Wizard-of-Oz textual comparison.**

No Pulse.  
No Unity.  
No 3D.

Two versions of the same splenic-rupture case:

### A. Traditional case

Static or conventional stepwise case.

### B. Consequence-based case

- scripted vital-sign deterioration,
- manual/Wizard state updates,
- learner choices,
- visible consequences,
- event timeline,
- debrief/retry discussion.

## Participants

Directional target:

- at least **5 clinical-phase learners**, and
- at least **3 clinicians / simulation educators**.

This is discovery, not an efficacy study.

## Questions

Ask:

- What did the consequence-based version teach that the traditional version did not?
- Which consequences changed your decisions?
- Was replay/debrief useful?
- Which parts felt like novelty rather than learning?
- What would make you use this again?
- What would prevent adoption?
- For educators: **what would this need to replace or complement your current tool?**

## Gate 0 STOP / PIVOT criteria

The current product hypothesis must be reworked if:

1. the majority of participants cannot articulate a learning benefit beyond novelty;
2. fewer than 2 of 3 educators would be willing to trial the concept assuming acceptable clinical accuracy/content;
3. the dominant educator feedback indicates that dynamic physiological consequences are not a meaningful adoption driver;
4. the required instructor/content workflow appears substantially more important than the proposed simulation capability and the current product direction does not address it.

Gate 0 is allowed to kill or substantially change the product thesis.

---

# 13. Gate A — Pulse Feasibility

Gate A is headless.

No Unity dependency.

## Required experiment

```text
Initialize patient
      ↓
Start internal/splenic hemorrhage
      ↓
Advance VPE-controlled simulation time
      ↓
Capture physiology
      ↓
Apply resuscitation
      ↓
Capture response
      ↓
Save/checkpoint state
      ↓
Reload/continue if supported
      ↓
Repeat identical runs
```

## Required Capability Matrix

For each item:

```text
SUPPORTED
PARTIAL
ABSENT
```

and workaround estimate:

```text
≤2 days
3–5 days
>5 days
```

Minimum rows:

- splenic/internal hemorrhage,
- heart rate output,
- BP/MAP output,
- blood volume/loss,
- respiratory/oxygenation outputs needed by the case,
- crystalloid,
- blood / PRBC,
- hemorrhage stop/control path,
- serialize/save state,
- load/restore state.

Optional capability rows:

- TXA,
- vasopressor,
- other later interventions.

## Gate A hard blockers for Pulse

Reject Pulse as the S0 physiology foundation if any of these is true:

1. VPE cannot reliably own simulation-time advancement;
2. the required hemorrhage trajectory or core outputs cannot be represented;
3. minimum resuscitation actions cannot be represented;
4. stable headless execution cannot be achieved;
5. required S0 functionality needs a workaround larger than the S0 spike budget;
6. clinical review finds the core trajectory unusable without changes large enough to defeat the reuse strategy.

Checkpoint/serialization failure does **not** automatically kill Pulse for S0; it may instead defer branch replay.

## Gate A output

- capability matrix,
- repeated-run results,
- trajectory CSV/JSON,
- save/load findings,
- known limitations,
- integration recommendation,
- ADR for process topology.

---

# 14. Pulse Integration ADR

At the end of Gate A, choose between:

## A. In-process

```text
Unity
  ↓
C#
  ↓
Pulse/native
```

## B. Separate VPE Runtime

```text
Unity
  ↓
IPC / local API
  ↓
VPE Runtime
  ↓
Pulse
```

Compare:

- time ownership,
- latency,
- headless testing,
- crash isolation,
- replay/checkpoint handling,
- future Unreal support,
- server execution,
- deployment,
- maintainability.

No final choice before Gate A evidence.

---

# 15. S0 Schedule Cap

S0 has a timebox.

## Target

**M10 within 20 weeks from implementation kickoff.**

## Hard boundary

**24 weeks.**

If M10 is not reached by week 24:

```text
STOP
or
RE-SCOPE
or
ARCHITECTURE PIVOT
```

No silent extension.

The timebox is a scope-control tool, not a promise of delivery.

---

# 16. Milestone Plan — v0.3

v0.3 deliberately reduces milestone fragmentation.

## M0A — Gate 0 Value Discovery

Wizard-of-Oz comparison + learner/educator discovery.

## M0B — Gate A Pulse Feasibility

Headless physiology spike + capability matrix + integration ADR.

**M0A and M0B run in parallel.**

---

## M1 — Two-Week Design Sprint

Single combined design sprint:

```text
Learning Objectives
→ Draft Rubric
→ Evidence Inventory
→ Interaction Inventory
→ Scenario Schema
→ Event Contract Draft
```

Exit:

- one coherent S0 case contract,
- no unresolved essential interaction category,
- no event field without a learning/evidence reason.

---

## M2 — Headless VPE Runtime

Build:

- simulation clock,
- command queue,
- Pulse adapter,
- scenario runtime,
- event/snapshot store,
- observation interfaces.

Exit:

- entire S0 physiology scenario runnable without Unity.

---

## M3 — Minimal Unity Client

Build only what S0 needs:

- patient view,
- vital monitor,
- structured clinical controls,
- scenario state,
- result display.

Exit:

- Unity round-trip works through VPE.

---

## M4 — FAST Spatial Interaction

Build:

- probe interaction,
- Anatomy Target Resolver,
- valid/invalid target logic,
- FAST observation generation,
- structured evidence event.

Exit:

- one complete 3D → clinical-evidence chain.

---

## M5 — Structured History + AI Patient

Build:

- clinical-intent taxonomy,
- structured selection,
- optional natural-language intent mapping,
- constrained AI patient response.

Exit:

- history remains grounded and evidence remains structured.

---

## M6 — Formative Assessment + Replay

Build:

- canonical replay,
- timeline,
- rubric evidence extraction,
- AI debrief grounded in evidence,
- retry/checkpoint only if Gate A supports it.

Exit:

- learner can understand what happened and why.

---

## M7 — S0 Medical + Educational Validation

Review:

- physiology trajectory,
- diagnostic observations,
- treatment effects,
- history responses,
- FAST logic,
- timing assumptions,
- rubric/evidence,
- debrief.

Decision:

```text
GO
REWORK
STOP
```

---

# 17. Build vs Reuse

| Component | Strategy | Candidate |
|---|---|---|
| VPE orchestration | Build | Custom |
| Simulation clock | Build | VPE-owned |
| Command queue | Build | Custom |
| Event/evidence store | Build | Custom |
| Scenario schema/runtime | Build | Custom |
| Observation layer | Build | Custom |
| Anatomy Target Resolver | Build | Narrow S0 implementation |
| Assessment evidence | Build | Custom |
| Physiology | Reuse/wrap | Pulse |
| 3D client | Reuse | Unity |
| AI patient language | Reuse model + constraints | Provider abstraction |
| Intent mapping | Structured first, optional model | Provider abstraction |
| AI debrief | Existing model + evidence grounding | Provider abstraction |
| Anatomy assets | Reuse/process | License-reviewed |
| Tissue biomechanics | Defer | iMSTK/SOFA later |
| Patient-specific CT | Defer | TotalSegmentator later |

---

# 18. Initial Customer Hypothesis

Primary institutional customer hypothesis:

> **Medical schools and medical simulation centers**

Primary learner:

> **Clinical-phase medical students**

First-class product stakeholder:

> **Instructor / simulation educator**

This makes these future platform capabilities strategically important:

- scenario authoring,
- assignment,
- instructor review,
- cohort analytics,
- curriculum mapping,
- reporting.

They are not all S0 requirements.

---

# 19. Licensing / Provenance

Every external artifact requires recorded provenance:

- source,
- version,
- license,
- commercial-use terms,
- attribution,
- derivative restrictions,
- modifications.

No dataset, model, or 3D asset enters the product merely because it is publicly downloadable.

---

# 20. Regulatory Position

S0 is positioned as:

```text
Education
Training
Simulation
Formative feedback
```

Not:

```text
Clinical decision support
Real-patient treatment advice
Medical device
High-stakes learner assessment
```

Assessment Mode remains deferred to S1.

Formal regulatory review is required before any consequential institutional scoring or progression decisions.

---

# 21. Core Moat Hypothesis

The integration layer remains a technical moat hypothesis:

```text
Clinical Action
→ Simulation
→ Observation
→ Structured Evidence
→ Debrief
```

However, v0.3 explicitly treats these as potentially stronger long-term moats:

- validated scenario content,
- scenario authoring workflow,
- instructor workflow,
- curriculum mapping,
- evidence-based learner data,
- accumulated educational validation.

Gate 0 must test this directly with educators.

---

# 22. S0 Non-Goals

S0 does not include:

- free-form surgery,
- induced injury,
- tissue cutting,
- deformable tissue,
- suturing,
- haptics,
- multiple spatial 3D procedure systems,
- whole-body anatomy,
- patient-specific CT,
- pediatric patients,
- pregnancy,
- broad pharmacology,
- full trauma curriculum,
- high-stakes assessment,
- autonomous AI grading,
- regulatory certification.

---

# 23. Risk-Control Rules

1. No LLM-owned medical truth.
2. No LLM-owned authoritative score.
3. No new subsystem without a concrete S0 learning requirement.
4. Exactly one required S0 spatial 3D interaction: FAST.
5. No claim of deterministic replay before evidence.
6. Assessment requirements precede event-schema freeze.
7. Pulse has one runtime owner.
8. Simulation time excludes system/model latency.
9. Every external dependency has provenance.
10. Gate 0 and Gate A must be capable of failure.
11. Week 24 forces stop/re-scope review.
12. Scenario architecture must move toward non-programmer authoring.
13. S0 ships Learning Mode only.

---

# 24. Active Decisions Incorporated

Existing decisions:

- `#900` — S0 excludes surgical injury generation.
- `#901` — VPE owns simulation time.
- `#902` — Replay uses recordings/checkpoints, not unproven determinism.
- `#903` — Assessment rubric precedes event schema.
- `#904` — Initial ICP is medical schools / simulation centers.
- `#905` — Gate 0 Value Discovery runs in parallel with Gate A.

Proposed v0.3 decisions:

- `DEC-007` — S0 delivery cap + milestone consolidation.
- `DEC-008` — Explicit STOP criteria + Pulse capability matrix.
- `DEC-009` — FAST is the only required spatial 3D interaction in S0.
- `DEC-010` — S0 ships Learning Mode only; Assessment Mode moves to S1.
- `DEC-011` — S0 history-taking uses structured clinical intents.

---

# 25. v0.3 Frozen Baseline

```text
Project                 = Nexora VPE
Initial ICP             = Medical schools / simulation centers
Primary learner         = Clinical-phase medical student
First domain            = Abdominal trauma
First case              = Splenic rupture + hemorrhagic shock
S0 mode                 = Learning Mode only
Physiology candidate    = Pulse, pending Gate A
3D engine               = Unity
Required spatial 3D     = FAST probe placement only
History                 = Structured clinical intents
Simulation clock        = VPE-owned
Replay                  = Recorded evidence + optional checkpoints + regression
Assessment              = Formative, structured-evidence-first
AI authority            = Non-authoritative
Gate 0                  = Wizard-of-Oz value discovery
Gate A                  = Headless Pulse feasibility
S0 target               = 20 weeks
S0 hard review boundary = 24 weeks
```

Unresolved by design:

```text
Pulse process topology
Final VPE implementation language
Final anatomy asset source
Checkpoint viability
Advanced pharmacology
Assessment Mode policy
SOFA vs iMSTK
VR/haptics
Patient-specific anatomy
Surgical vertical slice
S2/S3 architecture
```

---

# 26. Versioning

History:

```text
#898 — v0.1 — historical
  ↓
#906 — v0.2 — superseded by v0.3
  ↓
v0.3 — proposed active baseline
```

Once v0.3 is accepted:

- `#906` should become `superseded` or `archived`,
- v0.3 becomes the active reference baseline,
- DEC-007 → DEC-011 remain separate rationale records and are linked as implemented by v0.3.

Do not patch v0.2 further.

---

**End — Nexora VPE Master Plan v0.3**
