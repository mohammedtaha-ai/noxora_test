"""Tenant-aware boundary contracts without coupling to the S0 runtime."""

from __future__ import annotations

from dataclasses import dataclass

from .ids import require_identifier


class TenantContractError(ValueError):
    """Raised when tenant-scoped boundary data is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class TenantScope:
    """The explicit ownership boundary carried by platform contracts.

    This type is deliberately not an authentication credential.  Authorization
    must be performed by a trusted Control Plane before a command or record is
    accepted at a platform boundary.
    """

    tenant_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", require_identifier(self.tenant_id, field_name="tenant_id"))


@dataclass(frozen=True, slots=True)
class TenantEntityRef:
    """Reference to a tenant-owned entity suitable for audit and event routing."""

    scope: TenantScope
    entity_type: str
    entity_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.entity_type, str) or not self.entity_type.strip():
            raise TenantContractError("entity_type must be a nonempty string")
        normalized_type = self.entity_type.strip()
        if len(normalized_type) > 64 or any(character.isspace() for character in normalized_type):
            raise TenantContractError("entity_type must be a short whitespace-free string")
        object.__setattr__(self, "entity_type", normalized_type)
        object.__setattr__(self, "entity_id", require_identifier(self.entity_id, field_name="entity_id"))
