package session

import (
	"time"

	"github.com/google/uuid"
)

type State string

const (
	StateRequested     State = "REQUESTED"
	StatePendingWorker State = "PENDING_WORKER"
	StateFailed        State = "FAILED"
	StateCancelled     State = "CANCELLED"
)

func (s State) LeaseEligible() bool {
	return s == StatePendingWorker
}

func (s State) CanTransitionTo(next State) bool {
	switch s {
	case StateRequested:
		return next == StatePendingWorker || next == StateFailed || next == StateCancelled
	case StatePendingWorker:
		return next == StateFailed || next == StateCancelled
	default:
		return false
	}
}

type Session struct {
	ID                     uuid.UUID
	EventID                uuid.UUID
	CommandID              uuid.UUID
	TenantID               uuid.UUID
	AssignmentID           uuid.UUID
	ScenarioVersionID      uuid.UUID
	ScenarioArtifactID     uuid.UUID
	ScenarioArtifactSHA256 string
	RuntimeContractVersion string
	ExecutionManifest      map[string]any
	State                  State
	Generation             int64
	CreatedAt              time.Time
	UpdatedAt              time.Time
}

type AllocationResult struct {
	Session   Session
	Duplicate bool
}

type Lease struct {
	SessionID       uuid.UUID
	OwnerID         string
	LeaseToken      uuid.UUID
	LeaseGeneration int64
	LeaseExpiresAt  time.Time
	UpdatedAt       time.Time
}

type LeaseClaimResult struct {
	Lease     Lease
	Reclaimed bool
}
