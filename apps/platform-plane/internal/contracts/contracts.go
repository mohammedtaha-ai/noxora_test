package contracts

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"github.com/santhosh-tekuri/jsonschema/v6"
)

const (
	SimulationStartEventType = "control.simulation_start.requested"
	SchemaVersionV1          = 1
	envelopeSchemaID         = "https://nexora.example/schemas/platform-event-envelope/v1"
	simulationStartSchemaID  = "https://nexora.example/contracts/events/control.simulation_start.requested/v1/payload"
)

type Validator struct {
	envelope        *jsonschema.Schema
	simulationStart *jsonschema.Schema
}

type Event struct {
	EventID               uuid.UUID
	CommandID             uuid.UUID
	TenantID              uuid.UUID
	AssignmentID          uuid.UUID
	ScenarioID            uuid.UUID
	ArtifactID            uuid.UUID
	EventType             string
	SchemaVersion         int
	OccurredAt            time.Time
	PayloadHash           string
	ImmutableEnvelopeHash string
	Payload               map[string]any
	Manifest              map[string]any
	ArtifactSHA256        string
	RuntimeVersion        string
}

type ValidationError struct {
	Code string
	Err  error
}

func (e *ValidationError) Error() string {
	return e.Code
}

func (e *ValidationError) Unwrap() error {
	return e.Err
}

func Load(repositoryRoot string) (*Validator, error) {
	envelopePath := filepath.Join(repositoryRoot, "schemas", "platform-event-envelope.schema.json")
	payloadPath := filepath.Join(repositoryRoot, "contracts", "events", "control.simulation_start.requested.v1.schema.json")

	envelopeDocument, err := loadJSON(envelopePath)
	if err != nil {
		return nil, fmt.Errorf("load canonical envelope schema: %w", err)
	}
	payloadDocument, err := loadJSON(payloadPath)
	if err != nil {
		return nil, fmt.Errorf("load canonical simulation-start schema: %w", err)
	}

	compiler := jsonschema.NewCompiler()
	compiler.AssertFormat()
	if err := compiler.AddResource(envelopeSchemaID, envelopeDocument); err != nil {
		return nil, fmt.Errorf("register canonical envelope schema: %w", err)
	}
	if err := compiler.AddResource(simulationStartSchemaID, payloadDocument); err != nil {
		return nil, fmt.Errorf("register canonical simulation-start schema: %w", err)
	}
	envelope, err := compiler.Compile(envelopeSchemaID)
	if err != nil {
		return nil, fmt.Errorf("compile canonical envelope schema: %w", err)
	}
	simulationStart, err := compiler.Compile(simulationStartSchemaID)
	if err != nil {
		return nil, fmt.Errorf("compile canonical simulation-start schema: %w", err)
	}
	return &Validator{envelope: envelope, simulationStart: simulationStart}, nil
}

func (v *Validator) Validate(raw []byte) (Event, error) {
	instance, err := jsonschema.UnmarshalJSON(bytes.NewReader(raw))
	if err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}
	if err := v.envelope.Validate(instance); err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}
	envelope, ok := instance.(map[string]any)
	if !ok {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("envelope is not an object")}
	}

	eventType, _ := envelope["event_type"].(string)
	schemaVersion, ok := integer(envelope["schema_version"])
	if !ok || eventType != SimulationStartEventType || schemaVersion != SchemaVersionV1 {
		return Event{}, &ValidationError{Code: "UNSUPPORTED_SCHEMA", Err: fmt.Errorf("unsupported event type or schema version")}
	}
	payload, ok := envelope["payload"].(map[string]any)
	if !ok {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("payload is not an object")}
	}
	if err := v.simulationStart.Validate(payload); err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}

	manifest, ok := payload["execution_manifest"].(map[string]any)
	if !ok {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("execution manifest is not an object")}
	}
	artifact, ok := manifest["artifact"].(map[string]any)
	if !ok {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("artifact is not an object")}
	}

	eventID, err := parseUUID(envelope, "event_id")
	if err != nil {
		return Event{}, err
	}
	tenantID, err := parseUUID(envelope, "tenant_id")
	if err != nil {
		return Event{}, err
	}
	commandID, err := parseUUID(payload, "command_id")
	if err != nil {
		return Event{}, err
	}
	assignmentID, err := parseUUID(payload, "assignment_id")
	if err != nil {
		return Event{}, err
	}
	scenarioID, err := parseUUID(payload, "scenario_version_id")
	if err != nil {
		return Event{}, err
	}
	artifactID, err := parseUUID(artifact, "artifact_id")
	if err != nil {
		return Event{}, err
	}
	occurredAt, err := time.Parse(time.RFC3339Nano, envelope["occurred_at"].(string))
	if err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}
	payloadHash, err := hashJSON(payload)
	if err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}
	immutableEnvelopeHash, err := hashJSON(map[string]any{
		"event_id":       envelope["event_id"],
		"command_id":     payload["command_id"],
		"tenant_id":      envelope["tenant_id"],
		"event_type":     envelope["event_type"],
		"schema_version": envelope["schema_version"],
		"producer":       envelope["producer"],
		"aggregate_type": envelope["aggregate_type"],
		"aggregate_id":   envelope["aggregate_id"],
		"routing_key":    envelope["routing_key"],
		"classification": envelope["classification"],
		"payload":        payload,
	})
	if err != nil {
		return Event{}, &ValidationError{Code: "INVALID_EVENT", Err: err}
	}
	artifactSHA256, _ := artifact["sha256"].(string)
	runtimeVersion, _ := manifest["runtime_contract_version"].(string)

	return Event{
		EventID:               eventID,
		CommandID:             commandID,
		TenantID:              tenantID,
		AssignmentID:          assignmentID,
		ScenarioID:            scenarioID,
		ArtifactID:            artifactID,
		EventType:             eventType,
		SchemaVersion:         schemaVersion,
		OccurredAt:            occurredAt.UTC(),
		PayloadHash:           payloadHash,
		ImmutableEnvelopeHash: immutableEnvelopeHash,
		Payload:               payload,
		Manifest:              manifest,
		ArtifactSHA256:        artifactSHA256,
		RuntimeVersion:        runtimeVersion,
	}, nil
}

func loadJSON(path string) (any, error) {
	contents, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return jsonschema.UnmarshalJSON(bytes.NewReader(contents))
}

func parseUUID(values map[string]any, key string) (uuid.UUID, error) {
	value, ok := values[key].(string)
	if !ok {
		return uuid.Nil, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("%s is not a string UUID", key)}
	}
	parsed, err := uuid.Parse(value)
	if err != nil {
		return uuid.Nil, &ValidationError{Code: "INVALID_EVENT", Err: fmt.Errorf("%s is malformed", key)}
	}
	return parsed, nil
}

func integer(value any) (int, bool) {
	switch number := value.(type) {
	case int:
		return number, true
	case int64:
		return int(number), true
	case json.Number:
		parsed, err := number.Int64()
		if err == nil {
			return int(parsed), true
		}
	case float64:
		if number == float64(int(number)) {
			return int(number), true
		}
	}
	return 0, false
}

func hashJSON(value any) (string, error) {
	encoded, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(encoded)
	return hex.EncodeToString(digest[:]), nil
}
