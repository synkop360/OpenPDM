"""Replaceable immutable storage adapter for validated plugin packages."""

from __future__ import annotations

import os
from pathlib import Path

from openpdm.infrastructure.settings import Settings


class PluginPackageStorage:
    """Store packages by digest without exposing arbitrary filesystem paths."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, digest: str, archive: bytes) -> str:
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("Invalid plugin package digest.")
        target = (self.root / f"{digest}.openpdm-plugin").resolve()
        if target.parent != self.root:
            raise ValueError("Invalid plugin package storage path.")
        if target.exists():
            if target.read_bytes() != archive:
                raise ValueError("Stored plugin package does not match its digest.")
            return str(target)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(target, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(archive)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return str(target)

    def read(self, digest: str) -> bytes:
        target = (self.root / f"{digest}.openpdm-plugin").resolve()
        if target.parent != self.root or not target.is_file():
            raise FileNotFoundError("Plugin package is not installed.")
        return target.read_bytes()


def build_plugin_package_storage(settings: Settings | None = None) -> PluginPackageStorage:
    return PluginPackageStorage((settings or Settings()).plugin_package_root)
