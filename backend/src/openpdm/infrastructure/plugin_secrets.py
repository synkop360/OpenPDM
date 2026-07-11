"""Encryption adapter for deployment-scoped plugin configuration secrets."""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken


class PluginSecretCipher:
    def __init__(self, key: str | None) -> None:
        self._cipher = Fernet(key.encode("ascii")) if key else None

    def encrypt(self, values: dict[str, object]) -> str | None:
        if not values:
            return None
        if self._cipher is None:
            raise ValueError("OPENPDM_PLUGIN_CONFIGURATION_KEY is required for secret values.")
        payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        return self._cipher.encrypt(payload).decode("ascii")

    def decrypt(self, token: str | None) -> dict[str, object]:
        if token is None:
            return {}
        if self._cipher is None:
            raise ValueError("OPENPDM_PLUGIN_CONFIGURATION_KEY is required to decrypt secrets.")
        try:
            value = json.loads(self._cipher.decrypt(token.encode("ascii")))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Plugin configuration secrets cannot be decrypted.") from exc
        if not isinstance(value, dict):
            raise ValueError("Plugin configuration secret payload is invalid.")
        return value
