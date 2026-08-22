"""Distributed, time-sortable identifier primitives for platform boundaries.

This module intentionally does not provide authorization semantics or a global
ordering guarantee.  A UUIDv7 value is an opaque identifier; its time prefix
only provides useful locality and a per-generator monotonic ordering aid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
import time
import uuid


class IdentifierError(ValueError):
    """Raised when an identifier is malformed or cannot be generated safely."""


_UUID7_RANDOM_BITS = 74
_UUID7_RANDOM_LIMIT = (1 << _UUID7_RANDOM_BITS) - 1


def parse_uuid7(value: str) -> uuid.UUID:
    """Parse and validate an RFC 9562 UUIDv7 textual identifier."""

    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise IdentifierError("identifier must be a UUID string") from exc
    if parsed.version != 7:
        raise IdentifierError("identifier must use UUID version 7")
    if parsed.variant != uuid.RFC_4122:
        raise IdentifierError("identifier must use the RFC 4122 variant")
    return parsed


def require_identifier(value: str, *, field_name: str) -> str:
    """Validate a nonempty, bounded, opaque platform identifier string."""

    if not isinstance(value, str) or not value.strip():
        raise IdentifierError(f"{field_name} must be a nonempty string")
    normalized = value.strip()
    if len(normalized) > 128:
        raise IdentifierError(f"{field_name} exceeds 128 characters")
    return normalized


@dataclass(slots=True)
class Uuid7Generator:
    """Generate UUIDv7 identifiers with a per-process monotonic sequence.

    The generator follows the RFC 9562 field layout.  When multiple IDs are
    generated inside one millisecond, a 74-bit random tail is monotonically
    advanced within this generator instance.  This is deliberately *not* a
    cross-process total-order claim and callers must not infer authorization or
    simulation chronology from an ID.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_timestamp_ms: int = field(default=-1, init=False, repr=False)
    _last_random: int = field(default=-1, init=False, repr=False)

    def new(self) -> str:
        """Return one canonical lowercase UUIDv7 string."""

        now_ms = time.time_ns() // 1_000_000
        if now_ms < 0 or now_ms >= (1 << 48):
            raise IdentifierError("current time cannot be represented by UUIDv7")

        with self._lock:
            timestamp_ms = max(now_ms, self._last_timestamp_ms)
            random_bits = secrets.randbits(_UUID7_RANDOM_BITS)
            if timestamp_ms == self._last_timestamp_ms:
                if self._last_random >= _UUID7_RANDOM_LIMIT:
                    raise IdentifierError("UUIDv7 per-millisecond sequence exhausted")
                random_bits = max(random_bits, self._last_random + 1)

            random_a = random_bits >> 62
            random_b = random_bits & ((1 << 62) - 1)
            raw = (
                (timestamp_ms << 80)
                | (0x7 << 76)
                | (random_a << 64)
                | (0b10 << 62)
                | random_b
            )
            identifier = uuid.UUID(int=raw)
            self._last_timestamp_ms = timestamp_ms
            self._last_random = random_bits
            return str(identifier)


_DEFAULT_GENERATOR = Uuid7Generator()


def new_uuid7() -> str:
    """Return a process-default UUIDv7 identifier."""

    return _DEFAULT_GENERATOR.new()
