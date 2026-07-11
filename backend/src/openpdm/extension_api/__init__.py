"""Versioned public contract used equally by Official Plugins and Community Plugins."""

from .contracts import (
    EXTENSION_API_MAJOR_VERSION,
    EXTENSION_API_VERSION,
    AssetProviderCommand,
    Capability,
    EventEnvelope,
    ExtensionContext,
    ExtensionError,
    InvocationResponse,
    MetadataContribution,
    MetadataValueType,
)
from .manifest import ConfigurationProperty, ConfigurationSchema, PluginManifest
from .package import ValidatedPluginPackage, validate_plugin_package
from .sdk import build_plugin_package, inspect_plugin_package

__all__ = [
    "EXTENSION_API_MAJOR_VERSION",
    "EXTENSION_API_VERSION",
    "AssetProviderCommand",
    "Capability",
    "ConfigurationProperty",
    "ConfigurationSchema",
    "EventEnvelope",
    "ExtensionContext",
    "ExtensionError",
    "InvocationResponse",
    "MetadataContribution",
    "MetadataValueType",
    "PluginManifest",
    "ValidatedPluginPackage",
    "build_plugin_package",
    "inspect_plugin_package",
    "validate_plugin_package",
]
