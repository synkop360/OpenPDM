"""Strict manifest validation for immutable OpenPDM plugin packages."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import EXTENSION_API_MAJOR_VERSION, Capability

PLUGIN_ID_PATTERN = re.compile(
    r"^(?=.{3,255}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
EVENT_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,254}$")


class ConfigurationProperty(BaseModel):
    """Bounded Phase 4 configuration schema property."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(pattern=r"^(string|number|integer|boolean)$")
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    secret: bool = False
    default: str | int | float | bool | None = None


class ConfigurationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(default="object", pattern="^object$")
    properties: dict[str, ConfigurationProperty] = Field(default_factory=dict, max_length=100)
    required: list[str] = Field(default_factory=list, max_length=100)
    additionalProperties: bool = False

    @model_validator(mode="after")
    def required_properties_exist(self) -> ConfigurationSchema:
        missing = sorted(set(self.required) - set(self.properties))
        if missing:
            raise ValueError(
                f"Required configuration properties are undefined: {', '.join(missing)}"
            )
        return self


class PluginManifest(BaseModel):
    """Normative openpdm-plugin.json representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str = Field(min_length=1, max_length=255)
    version: str
    extension_api_versions: list[int] = Field(min_length=1, max_length=16)
    component: str
    capabilities: list[Capability] = Field(min_length=1, max_length=16)
    event_subscriptions: list[str] = Field(default_factory=list, max_length=100)
    configuration: ConfigurationSchema | None = None

    @field_validator("id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        if not PLUGIN_ID_PATTERN.fullmatch(value):
            raise ValueError("Plugin id must be a lowercase reverse-domain identifier.")
        return value

    @field_validator("version")
    @classmethod
    def valid_semver(cls, value: str) -> str:
        if not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("Plugin version must use semantic major.minor.patch form.")
        return value

    @field_validator("extension_api_versions")
    @classmethod
    def unique_api_versions(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value) or len(value) != len(set(value)):
            raise ValueError("Extension API versions must be unique positive integers.")
        return value

    @field_validator("component")
    @classmethod
    def safe_component_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError("Component must be a root-level package filename.")
        if path.suffix != ".wasm" or value in {"", ".", ".."}:
            raise ValueError("Component must identify a .wasm file.")
        return value

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[Capability]) -> list[Capability]:
        if len(value) != len(set(value)):
            raise ValueError("Capabilities must be unique.")
        return value

    @field_validator("event_subscriptions")
    @classmethod
    def valid_event_subscriptions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(
            not EVENT_TYPE_PATTERN.fullmatch(item) for item in value
        ):
            raise ValueError("Event subscriptions must be unique valid event type names.")
        return value

    @model_validator(mode="after")
    def coherent_capabilities(self) -> PluginManifest:
        if self.event_subscriptions and Capability.EVENT_HANDLER not in self.capabilities:
            raise ValueError("Event subscriptions require the event_handler capability.")
        return self

    @property
    def is_compatible(self) -> bool:
        return EXTENSION_API_MAJOR_VERSION in self.extension_api_versions

    @classmethod
    def from_json(cls, payload: bytes, *, max_bytes: int = 64 * 1024) -> PluginManifest:
        if len(payload) > max_bytes:
            raise ValueError("Plugin manifest exceeds the size limit.")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Plugin manifest is not valid UTF-8 JSON.") from exc
        return cls.model_validate(value)
