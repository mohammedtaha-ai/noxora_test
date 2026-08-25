package config

import (
	"fmt"
	"net"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultListenAddr   = "127.0.0.1:8090"
	defaultLease        = 30 * time.Second
	defaultMaxEventByte = int64(1 << 20)
)

type Config struct {
	DatabaseURL   string
	ListenAddr    string
	LogLevel      string
	LeaseDuration time.Duration
	MaxEventBytes int64
}

func Load() (Config, error) {
	leaseDuration, err := durationEnv("PLATFORM_LEASE_DURATION", defaultLease)
	if err != nil {
		return Config{}, err
	}
	maxEventBytes, err := int64Env("PLATFORM_MAX_EVENT_BYTES", defaultMaxEventByte)
	if err != nil {
		return Config{}, err
	}

	config := Config{
		DatabaseURL:   strings.TrimSpace(os.Getenv("DATABASE_URL")),
		ListenAddr:    valueOrDefault("PLATFORM_LISTEN_ADDR", defaultListenAddr),
		LogLevel:      strings.ToLower(valueOrDefault("PLATFORM_LOG_LEVEL", "info")),
		LeaseDuration: leaseDuration,
		MaxEventBytes: maxEventBytes,
	}
	if err := config.Validate(); err != nil {
		return Config{}, err
	}
	return config, nil
}

func (c Config) Validate() error {
	if c.DatabaseURL == "" {
		return fmt.Errorf("DATABASE_URL is required")
	}
	parsed, err := url.Parse(c.DatabaseURL)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return fmt.Errorf("DATABASE_URL must be a valid absolute PostgreSQL URL")
	}
	if parsed.Scheme != "postgres" && parsed.Scheme != "postgresql" {
		return fmt.Errorf("DATABASE_URL must use postgres or postgresql scheme")
	}
	if err := validateLoopbackAddress(c.ListenAddr); err != nil {
		return err
	}
	if c.LeaseDuration <= 0 || c.LeaseDuration > 24*time.Hour {
		return fmt.Errorf("PLATFORM_LEASE_DURATION must be greater than zero and at most 24h")
	}
	if c.MaxEventBytes <= 0 || c.MaxEventBytes > 8<<20 {
		return fmt.Errorf("PLATFORM_MAX_EVENT_BYTES must be greater than zero and at most 8MiB")
	}
	if c.LogLevel != "debug" && c.LogLevel != "info" && c.LogLevel != "warn" && c.LogLevel != "error" {
		return fmt.Errorf("PLATFORM_LOG_LEVEL must be debug, info, warn, or error")
	}
	return nil
}

func validateLoopbackAddress(address string) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil || host == "" {
		return fmt.Errorf("PLATFORM_LISTEN_ADDR must be host:port")
	}
	if strings.EqualFold(host, "localhost") {
		return nil
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return fmt.Errorf("PLATFORM_LISTEN_ADDR must bind loopback only")
	}
	return nil
}

func valueOrDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func durationEnv(key string, fallback time.Duration) (time.Duration, error) {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback, nil
	}
	parsed, err := time.ParseDuration(value)
	if err != nil {
		return 0, fmt.Errorf("%s must be a Go duration: %w", key, err)
	}
	return parsed, nil
}

func int64Env(key string, fallback int64) (int64, error) {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback, nil
	}
	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer: %w", key, err)
	}
	return parsed, nil
}
