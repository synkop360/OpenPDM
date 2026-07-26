"""OpenPDM backend package."""

from __future__ import annotations

import os
import platform

if os.name == "nt":
    os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

    def _safe_machine() -> str:
        """Avoid slow WMI platform probing on some Windows environments."""
        return os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64")

    platform.machine = _safe_machine  # type: ignore[assignment]

__all__ = ["__version__"]

__version__ = "0.0.0"
