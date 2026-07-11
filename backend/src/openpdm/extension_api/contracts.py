"""Public Extension API v1 contracts shared by the Platform Core and plugins."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

EXTENSION_API_MAJOR_VERSION = 1
EXTENSION_API_VERSION = "1"


class Capability(StrEnum):
    """Capabilities that may be declared by a Phase 4 plugin."""

    ASSET_PROVIDER = "asset_provider"
    METADATA_PROVIDER = "metadata_provider"
    EVENT_HANDLER = "event_handler"


class MetadataValueType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    JSON = "json"


class ExtensionContext(BaseModel):
    """Authorization context supplied by the Platform Core, never by a plugin."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=255)
    actor_id: str = Field(min_length=1, max_length=36)
    organization_id: str | None = Field(default=None, max_length=36)
    project_id: str | None = Field(default=None, max_length=36)


class MetadataContribution(BaseModel):
    """Domain-neutral metadata returned by a Metadata Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: Literal["asset", "revision", "representation"]
    target_id: str = Field(min_length=1, max_length=36)
    key: str = Field(min_length=1, max_length=255)
    value: object
    value_type: MetadataValueType


class AssetProviderCommand(BaseModel):
    """Generic command submitted by an Asset Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["create_asset", "create_revision", "create_representation"]
    context: ExtensionContext
    payload: dict[str, object]


class EventEnvelope(BaseModel):
    """Post-commit event delivered to an event-handler capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=36)
    event_type: str = Field(min_length=1, max_length=255)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    context: ExtensionContext
    payload: dict[str, object]


class ExtensionError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]
    message: str = Field(min_length=1, max_length=1024)
    retryable: bool = False


class InvocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    success: bool
    metadata: list[MetadataContribution] = Field(default_factory=list, max_length=1000)
    commands: list[AssetProviderCommand] = Field(default_factory=list, max_length=100)
    error: ExtensionError | None = None
