"""Hostile-input-safe validation for OpenPDM plugin package archives."""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from .manifest import PluginManifest

MANIFEST_NAME = "openpdm-plugin.json"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 8
WASM_COMPONENT_HEADER = b"\x00asm\x0d\x00\x01\x00"


@dataclass(frozen=True, slots=True)
class ValidatedPluginPackage:
    manifest: PluginManifest
    digest: str
    component: bytes
    archive: bytes


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or ".." in path.parts
        or len(path.parts) != 1
        or name.endswith("/")
    ):
        raise ValueError(f"Unsafe plugin package entry: {name!r}.")


def validate_plugin_package(archive: bytes) -> ValidatedPluginPackage:
    """Validate an entire package before any content is persisted or executed."""

    if not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError("Plugin package is empty or exceeds the archive size limit.")

    try:
        package = ZipFile(BytesIO(archive))
    except BadZipFile as exc:
        raise ValueError("Plugin package is not a valid ZIP archive.") from exc

    with package:
        members = package.infolist()
        if not 1 <= len(members) <= MAX_ENTRIES:
            raise ValueError("Plugin package contains an invalid number of entries.")
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ValueError("Plugin package contains duplicate entries.")

        total_size = 0
        for member in members:
            _validate_member_name(member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or stat.S_ISDIR(mode):
                raise ValueError("Plugin package links and directories are forbidden.")
            if member.file_size > MAX_ENTRY_BYTES:
                raise ValueError("Plugin package entry exceeds the size limit.")
            total_size += member.file_size
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Plugin package exceeds the uncompressed size limit.")

        if MANIFEST_NAME not in names:
            raise ValueError(f"Plugin package must contain {MANIFEST_NAME}.")
        manifest = PluginManifest.from_json(package.read(MANIFEST_NAME))
        if not manifest.is_compatible:
            raise ValueError("Plugin does not support Extension API v1.")
        allowed = {MANIFEST_NAME, manifest.component}
        unexpected = sorted(set(names) - allowed)
        if unexpected:
            raise ValueError(f"Plugin package contains unexpected entries: {', '.join(unexpected)}")
        if manifest.component not in names:
            raise ValueError("Plugin package does not contain the declared WebAssembly Component.")

        component = package.read(manifest.component)
        if not component.startswith(WASM_COMPONENT_HEADER):
            raise ValueError("Declared component is not a WebAssembly Component binary.")

    return ValidatedPluginPackage(
        manifest=manifest,
        digest=hashlib.sha256(archive).hexdigest(),
        component=component,
        archive=archive,
    )
