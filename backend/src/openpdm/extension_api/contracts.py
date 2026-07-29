"""Public Extension API v1 contracts shared by the Platform Core and plugins."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXTENSION_API_MAJOR_VERSION = 1
EXTENSION_API_VERSION = "1"


class Capability(StrEnum):
    """Capabilities that may be declared by a Phase 4 plugin."""

    ASSET_PROVIDER = "asset_provider"
    METADATA_PROVIDER = "metadata_provider"
    OPTION_PROVIDER = "option_provider"
    EVENT_HANDLER = "event_handler"
    ANALYSIS_PROVIDER = "analysis_provider"


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


class RepresentationAnalysisInput(BaseModel):
    """Bounded, authorized representation content supplied for provider analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    representation_id: str = Field(min_length=1, max_length=36)
    asset_id: str = Field(min_length=1, max_length=36)
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0, le=5 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_base64: str = Field(min_length=1, max_length=7_000_000)


class ReferenceContribution(BaseModel):
    """A generic Reference supplied by an Analysis Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_key: str = Field(min_length=1, max_length=255)
    source_asset_id: str = Field(min_length=1, max_length=36)
    reference_type: str = Field(min_length=1, max_length=255)
    target_uri: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)


class RelationshipContribution(BaseModel):
    """A generic Asset Graph relationship supplied by an Analysis Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_key: str = Field(min_length=1, max_length=255)
    source_asset_id: str = Field(min_length=1, max_length=36)
    target_asset_id: str = Field(min_length=1, max_length=36)
    relationship_type: str = Field(min_length=1, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def target_differs_from_source(self) -> RelationshipContribution:
        if self.source_asset_id == self.target_asset_id:
            raise ValueError("Relationship source and target Assets must differ.")
        return self


class AssetProviderCommand(BaseModel):
    """Generic command submitted by an Asset Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["create_asset", "create_revision", "create_representation"]
    context: ExtensionContext
    payload: dict[str, object]


class ProviderOption(BaseModel):
    """One safe, declarative option supplied by an Option Provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)


class ProviderOptionSet(BaseModel):
    """A bounded set of plugin-owned choices with no executable presentation content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)
    options: list[ProviderOption] = Field(min_length=1, max_length=100)


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
    references: list[ReferenceContribution] = Field(default_factory=list, max_length=1000)
    relationships: list[RelationshipContribution] = Field(default_factory=list, max_length=1000)
    commands: list[AssetProviderCommand] = Field(default_factory=list, max_length=100)
    option_sets: list[ProviderOptionSet] = Field(default_factory=list, max_length=20)
    error: ExtensionError | None = None
