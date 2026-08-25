package contracts

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestValidatorAcceptsSharedValidFixture(t *testing.T) {
	validator := testValidator(t)
	event, err := validator.Validate(readFixture(t, "simulation_start_requested_v1.valid.json"))
	if err != nil {
		t.Fatalf("validate shared valid fixture: %v", err)
	}
	if event.EventType != SimulationStartEventType || event.SchemaVersion != SchemaVersionV1 {
		t.Fatalf("unexpected event identity: %+v", event)
	}
	if event.CommandID.String() != "018f5f54-8c8e-7000-8000-000000000005" {
		t.Fatalf("unexpected parsed command id: %s", event.CommandID)
	}
}

func TestValidatorRejectsSharedInvalidFixtures(t *testing.T) {
	validator := testValidator(t)
	for _, filename := range []string{
		"simulation_start_requested_v1.invalid_extra_property.json",
		"simulation_start_requested_v1.invalid_uuid.json",
		"simulation_start_requested_v1.invalid_manifest.json",
	} {
		t.Run(filename, func(t *testing.T) {
			_, err := validator.Validate(readFixture(t, filename))
			assertValidationCode(t, err, "INVALID_EVENT")
		})
	}
}

func TestValidatorRejectsUnsupportedSchemaVersion(t *testing.T) {
	validator := testValidator(t)
	var fixture map[string]any
	if err := json.Unmarshal(readFixture(t, "simulation_start_requested_v1.valid.json"), &fixture); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}
	fixture["schema_version"] = 2
	mutated, err := json.Marshal(fixture)
	if err != nil {
		t.Fatalf("encode fixture: %v", err)
	}
	_, err = validator.Validate(mutated)
	assertValidationCode(t, err, "UNSUPPORTED_SCHEMA")
}

func testValidator(t *testing.T) *Validator {
	t.Helper()
	validator, err := Load(repositoryRoot(t))
	if err != nil {
		t.Fatalf("load canonical schemas: %v", err)
	}
	return validator
}

func readFixture(t *testing.T, filename string) []byte {
	t.Helper()
	contents, err := os.ReadFile(filepath.Join(repositoryRoot(t), "contracts", "fixtures", filename))
	if err != nil {
		t.Fatalf("read fixture %s: %v", filename, err)
	}
	return contents
}

func repositoryRoot(t *testing.T) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	return filepath.Clean(filepath.Join(workingDirectory, "..", "..", "..", ".."))
}

func assertValidationCode(t *testing.T, err error, want string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected validation error %s", want)
	}
	var validationError *ValidationError
	if !errors.As(err, &validationError) {
		t.Fatalf("expected ValidationError, got %T: %v", err, err)
	}
	if validationError.Code != want {
		t.Fatalf("validation code = %s, want %s", validationError.Code, want)
	}
}
