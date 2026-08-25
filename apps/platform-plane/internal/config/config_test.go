package config

import (
	"strings"
	"testing"
	"time"
)

func TestConfigValidationAcceptsLoopbackPostgres(t *testing.T) {
	configuration := Config{
		DatabaseURL:   "postgres://user:pass@127.0.0.1:5432/platform_test?sslmode=disable",
		ListenAddr:    "127.0.0.1:8090",
		LogLevel:      "info",
		LeaseDuration: time.Second,
		MaxEventBytes: 1024,
	}
	if err := configuration.Validate(); err != nil {
		t.Fatalf("validate safe configuration: %v", err)
	}
}

func TestConfigValidationRejectsUnsafeOrMalformedValues(t *testing.T) {
	base := Config{
		DatabaseURL:   "postgres://user:pass@127.0.0.1:5432/platform_test?sslmode=disable",
		ListenAddr:    "127.0.0.1:8090",
		LogLevel:      "info",
		LeaseDuration: time.Second,
		MaxEventBytes: 1024,
	}
	cases := []struct {
		name   string
		mutate func(*Config)
		want   string
	}{
		{"missing database", func(c *Config) { c.DatabaseURL = "" }, "DATABASE_URL"},
		{"wrong database scheme", func(c *Config) { c.DatabaseURL = "mysql://localhost/example" }, "postgres"},
		{"public bind", func(c *Config) { c.ListenAddr = "0.0.0.0:8090" }, "loopback"},
		{"invalid lease", func(c *Config) { c.LeaseDuration = 0 }, "LEASE_DURATION"},
		{"oversized maximum", func(c *Config) { c.MaxEventBytes = 9 << 20 }, "MAX_EVENT_BYTES"},
		{"invalid log level", func(c *Config) { c.LogLevel = "trace" }, "LOG_LEVEL"},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			configuration := base
			testCase.mutate(&configuration)
			if err := configuration.Validate(); err == nil || !strings.Contains(err.Error(), testCase.want) {
				t.Fatalf("Validate() error = %v, want substring %q", err, testCase.want)
			}
		})
	}
}
