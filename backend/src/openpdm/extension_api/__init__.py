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
    ProviderOption,
    ProviderOptionSet,
)
from .manifest import ConfigurationProperty, ConfigurationSchema, PluginManifest
from .package import ValidatedPluginPackage, validate_plugin_package
from .sdk import (
    build_plugin_package,
    extension_api_wit_path,
    inspect_plugin_package,
    scaffold_plugin,
)

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
    "ProviderOption",
    "ProviderOptionSet",
    "PluginManifest",
    "ValidatedPluginPackage",
    "build_plugin_package",
    "extension_api_wit_path",
    "inspect_plugin_package",
    "scaffold_plugin",
    "validate_plugin_package",
]
