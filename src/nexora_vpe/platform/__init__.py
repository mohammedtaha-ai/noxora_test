"""Scale-ready platform boundary abstractions.

These contracts are intentionally independent from the S0 VPE runtime.  They
provide local development/test primitives, not deployed infrastructure.
"""

from .events import (
    CollectingEventPublisher,
    DataClassification as EventDataClassification,
    EventPublisher,
    PlatformEvent,
    PlatformEventError,
)
from .ids import IdentifierError, Uuid7Generator, new_uuid7, parse_uuid7, require_identifier
from .object_storage import (
    ArtifactType,
    DataClassification as ArtifactDataClassification,
    LocalFilesystemObjectStorage,
    ObjectRecord,
    ObjectStorage,
    ObjectStorageError,
    RetentionClass,
)
from .outbox import OutboxClaim, OutboxError, OutboxRecord, SQLiteTransactionalOutbox
from .tenancy import TenantContractError, TenantEntityRef, TenantScope

__all__ = [
    "ArtifactDataClassification",
    "ArtifactType",
    "CollectingEventPublisher",
    "EventDataClassification",
    "EventPublisher",
    "IdentifierError",
    "LocalFilesystemObjectStorage",
    "ObjectRecord",
    "ObjectStorage",
    "ObjectStorageError",
    "OutboxClaim",
    "OutboxError",
    "OutboxRecord",
    "PlatformEvent",
    "PlatformEventError",
    "RetentionClass",
    "SQLiteTransactionalOutbox",
    "TenantContractError",
    "TenantEntityRef",
    "TenantScope",
    "Uuid7Generator",
    "new_uuid7",
    "parse_uuid7",
    "require_identifier",
]
