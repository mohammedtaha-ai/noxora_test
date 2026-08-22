"""Provider-neutral artifact storage contracts and a local development adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Protocol

from .ids import new_uuid7, require_identifier
from .tenancy import TenantScope


class ObjectStorageError(RuntimeError):
    """Raised when artifact storage violates the platform storage contract."""


class ArtifactType(str, Enum):
    SCENARIO_ASSET = "scenario_asset"
    SESSION_CHECKPOINT = "session_checkpoint"
    SESSION_REPLAY = "session_replay"
    SESSION_EXPORT = "session_export"
    RESEARCH_EXPORT = "research_export"
    TELEMETRY_BUNDLE = "telemetry_bundle"


class RetentionClass(str, Enum):
    PRODUCT_ASSET = "PRODUCT_ASSET"
    RESTRICTED_SESSION = "RESTRICTED_SESSION"
    USER_EXPORT = "USER_EXPORT"
    RESEARCH_GOVERNED = "RESEARCH_GOVERNED"
    OPERATIONS_BOUNDED = "OPERATIONS_BOUNDED"


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ObjectStorageError("metadata must be a mapping")
    copied = dict(value)
    try:
        encoded = json.dumps(copied, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ObjectStorageError("metadata must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 8_192:
        raise ObjectStorageError("metadata exceeds 8192 bytes")
    return copied


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    """Immutable metadata returned for an artifact stored through this contract."""

    object_id: str
    storage_key: str
    sha256: str
    byte_length: int
    content_type: str
    artifact_type: ArtifactType
    classification: DataClassification
    retention_class: RetentionClass
    scope: TenantScope
    created_at: datetime
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", require_identifier(self.object_id, field_name="object_id"))
        if not isinstance(self.storage_key, str) or not self.storage_key or self.storage_key.startswith("/"):
            raise ObjectStorageError("storage_key must be a relative nonempty key")
        key_path = Path(self.storage_key)
        if ".." in key_path.parts or len(key_path.parts) < 2:
            raise ObjectStorageError("storage_key must be a safe nested key")
        normalized_hash = self.sha256.lower()
        if len(normalized_hash) != 64 or any(char not in "0123456789abcdef" for char in normalized_hash):
            raise ObjectStorageError("sha256 must be a 64-character lowercase hexadecimal digest")
        object.__setattr__(self, "sha256", normalized_hash)
        if not isinstance(self.byte_length, int) or isinstance(self.byte_length, bool) or self.byte_length < 0:
            raise ObjectStorageError("byte_length must be a nonnegative integer")
        if not isinstance(self.content_type, str) or not self.content_type.strip() or len(self.content_type) > 128:
            raise ObjectStorageError("content_type must be a bounded nonempty string")
        object.__setattr__(self, "content_type", self.content_type.strip().lower())
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ObjectStorageError("created_at must be timezone-aware")
        object.__setattr__(self, "created_at", self.created_at.astimezone(timezone.utc))
        object.__setattr__(self, "metadata", _json_metadata(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["artifact_type"] = self.artifact_type.value
        values["classification"] = self.classification.value
        values["retention_class"] = self.retention_class.value
        values["scope"] = {"tenant_id": self.scope.tenant_id}
        values["created_at"] = self.created_at.isoformat().replace("+00:00", "Z")
        return values


class ObjectStorage(Protocol):
    """Artifact bytes API; callers own authorization before read/write operations."""

    def put(
        self,
        *,
        content: bytes,
        content_type: str,
        artifact_type: ArtifactType,
        classification: DataClassification,
        retention_class: RetentionClass,
        scope: TenantScope,
        metadata: Mapping[str, Any],
    ) -> ObjectRecord:
        """Store immutable bytes and return an immutable reference."""

    def get(self, record: ObjectRecord) -> bytes:
        """Read bytes addressed by a previously authorized record."""

    def verify(self, record: ObjectRecord) -> bool:
        """Verify byte length and SHA-256 without treating mismatch as usable."""


class LocalFilesystemObjectStorage:
    """Local filesystem development adapter, deliberately not a cloud emulator.

    The adapter uses content-addressed storage keys and atomically replaces a
    staging file.  It has no encryption, lifecycle daemon, signed URLs, or
    authorization service; production adapters must provide those concerns.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._objects = self._root / "objects"
        self._metadata = self._root / "metadata"
        self._staging = self._root / "staging"
        for directory in (self._objects, self._metadata, self._staging):
            directory.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        content: bytes,
        content_type: str,
        artifact_type: ArtifactType,
        classification: DataClassification,
        retention_class: RetentionClass,
        scope: TenantScope,
        metadata: Mapping[str, Any],
    ) -> ObjectRecord:
        """Write bytes once under a content hash and persist immutable metadata."""

        if not isinstance(content, bytes):
            raise ObjectStorageError("content must be bytes")
        if not isinstance(artifact_type, ArtifactType):
            raise ObjectStorageError("artifact_type must be an ArtifactType")
        if not isinstance(classification, DataClassification):
            raise ObjectStorageError("classification must be a DataClassification")
        if not isinstance(retention_class, RetentionClass):
            raise ObjectStorageError("retention_class must be a RetentionClass")
        digest = hashlib.sha256(content).hexdigest()
        storage_key = f"objects/{digest[:2]}/{digest}"
        object_path = self._resolve_storage_key(storage_key)
        metadata_path = self._metadata / f"{digest}.json"

        if object_path.exists() and metadata_path.exists():
            record = self._load_record(metadata_path)
            self._assert_same_contract(
                record,
                content_type=content_type,
                artifact_type=artifact_type,
                classification=classification,
                retention_class=retention_class,
                scope=scope,
                metadata=metadata,
            )
            return record
        if object_path.exists() != metadata_path.exists():
            raise ObjectStorageError("local artifact storage has an incomplete immutable record")

        object_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self._staging, delete=False) as handle:
            handle.write(content)
            temp_name = handle.name
        try:
            os.replace(temp_name, object_path)
            record = ObjectRecord(
                object_id=new_uuid7(),
                storage_key=storage_key,
                sha256=digest,
                byte_length=len(content),
                content_type=content_type,
                artifact_type=artifact_type,
                classification=classification,
                retention_class=retention_class,
                scope=scope,
                created_at=_utc_now(),
                metadata=metadata,
            )
            with tempfile.NamedTemporaryFile(dir=self._staging, delete=False, mode="w", encoding="utf-8") as handle:
                json.dump(record.as_dict(), handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                metadata_temp_name = handle.name
            try:
                os.replace(metadata_temp_name, metadata_path)
            except BaseException:
                object_path.unlink(missing_ok=True)
                raise
            return record
        finally:
            Path(temp_name).unlink(missing_ok=True)
            metadata_temp = locals().get("metadata_temp_name")
            if isinstance(metadata_temp, str):
                Path(metadata_temp).unlink(missing_ok=True)

    def get(self, record: ObjectRecord) -> bytes:
        """Return bytes only when the persisted record still matches integrity metadata."""

        self._ensure_known_record(record)
        content = self._resolve_storage_key(record.storage_key).read_bytes()
        if len(content) != record.byte_length or hashlib.sha256(content).hexdigest() != record.sha256:
            raise ObjectStorageError("artifact integrity verification failed")
        return content

    def verify(self, record: ObjectRecord) -> bool:
        """Return false for missing or tampered bytes without masking metadata errors."""

        self._ensure_known_record(record)
        path = self._resolve_storage_key(record.storage_key)
        if not path.exists():
            return False
        content = path.read_bytes()
        return len(content) == record.byte_length and hashlib.sha256(content).hexdigest() == record.sha256

    def _ensure_known_record(self, record: ObjectRecord) -> None:
        if not isinstance(record, ObjectRecord):
            raise ObjectStorageError("record must be an ObjectRecord")
        metadata_path = self._metadata / f"{record.sha256}.json"
        if not metadata_path.exists():
            raise ObjectStorageError("artifact metadata record does not exist")
        stored = self._load_record(metadata_path)
        if stored != record:
            raise ObjectStorageError("artifact record does not match immutable metadata")

    def _resolve_storage_key(self, storage_key: str) -> Path:
        candidate = (self._root / storage_key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ObjectStorageError("storage_key escapes local storage root") from exc
        return candidate

    @staticmethod
    def _assert_same_contract(
        record: ObjectRecord,
        *,
        content_type: str,
        artifact_type: ArtifactType,
        classification: DataClassification,
        retention_class: RetentionClass,
        scope: TenantScope,
        metadata: Mapping[str, Any],
    ) -> None:
        candidate_metadata = _json_metadata(metadata)
        if (
            record.content_type != content_type.strip().lower()
            or record.artifact_type is not artifact_type
            or record.classification is not classification
            or record.retention_class is not retention_class
            or record.scope != scope
            or dict(record.metadata) != candidate_metadata
        ):
            raise ObjectStorageError("same content cannot be rewritten with different immutable metadata")

    @staticmethod
    def _load_record(path: Path) -> ObjectRecord:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError) as exc:
            raise ObjectStorageError("stored artifact metadata is unreadable") from exc
        if not isinstance(value, Mapping):
            raise ObjectStorageError("stored artifact metadata must be an object")
        scope_value = value.get("scope")
        if not isinstance(scope_value, Mapping):
            raise ObjectStorageError("stored artifact scope is invalid")
        created_at = value.get("created_at")
        if not isinstance(created_at, str):
            raise ObjectStorageError("stored artifact timestamp is invalid")
        try:
            parsed_timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return ObjectRecord(
                object_id=str(value.get("object_id", "")),
                storage_key=str(value.get("storage_key", "")),
                sha256=str(value.get("sha256", "")),
                byte_length=value.get("byte_length"),
                content_type=str(value.get("content_type", "")),
                artifact_type=ArtifactType(str(value.get("artifact_type", ""))),
                classification=DataClassification(str(value.get("classification", ""))),
                retention_class=RetentionClass(str(value.get("retention_class", ""))),
                scope=TenantScope(tenant_id=str(scope_value.get("tenant_id", ""))),
                created_at=parsed_timestamp,
                metadata=value.get("metadata", {}),
            )
        except (TypeError, ValueError) as exc:
            raise ObjectStorageError("stored artifact metadata violates contract") from exc
