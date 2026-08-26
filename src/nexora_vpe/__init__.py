"""Nexora VPE S0 headless runtime.

The package records structured learning-simulation evidence. It does not offer
clinical decision support, patient-specific diagnosis, treatment advice, or
high-stakes assessment.
"""

from .adapter import DeterministicPhysiologyAdapter, PhysiologyAdapter
from .model import EventContractStatus, EventType, event_contract_status
from .runtime import VpeRuntime
from .scenario import S0Scenario
from .scenario_io import load_s0_scenario
from .pulse_adapter import PulseAdapter, PulseAdapterConfig, PulseAdapterError
from .client_facade import VpeClientFacade
from .local_transport import LocalFacadeHttpServer
from .host import TickResult, VpePacedHost
from .evidence_evaluator import EvaluationResult, EvidenceFinding, FindingStatus, evaluate_evidence, serialize_evaluation
from .replay import (
    CanonicalTimeline,
    RecordedSession,
    TimelineEntry,
    canonical_timeline,
    evaluate_recording,
    record_session,
    recorded_session_from_dict,
    serialize_recorded_session,
    serialize_timeline,
)
from .client_contracts import (
    ClientCommandStatus,
    ClientError,
    ClientErrorCode,
    ClientEvent,
    ClientRuntimeState,
    ClientScenarioManifest,
    ClientSnapshot,
    CommandAccepted,
    CommandOutcome,
    CommandRequest,
)

__all__ = [
    "DeterministicPhysiologyAdapter",
    "EventContractStatus",
    "EventType",
    "event_contract_status",
    "PhysiologyAdapter",
    "S0Scenario",
    "VpeRuntime",
    "load_s0_scenario",
    "PulseAdapter",
    "PulseAdapterConfig",
    "PulseAdapterError",
    "VpeClientFacade",
    "LocalFacadeHttpServer",
    "TickResult",
    "VpePacedHost",
    "EvaluationResult",
    "EvidenceFinding",
    "FindingStatus",
    "evaluate_evidence",
    "serialize_evaluation",
    "CanonicalTimeline",
    "RecordedSession",
    "TimelineEntry",
    "canonical_timeline",
    "evaluate_recording",
    "record_session",
    "recorded_session_from_dict",
    "serialize_recorded_session",
    "serialize_timeline",
    "ClientCommandStatus",
    "ClientError",
    "ClientErrorCode",
    "ClientEvent",
    "ClientRuntimeState",
    "ClientScenarioManifest",
    "ClientSnapshot",
    "CommandAccepted",
    "CommandOutcome",
    "CommandRequest",
]
