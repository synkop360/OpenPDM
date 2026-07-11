"""One-request JSON worker process for WebAssembly Component execution."""

from __future__ import annotations

import base64
import json
import sys
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field

from .sandbox import SandboxLimits, WasmtimeSandbox

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 24 * 1024 * 1024


class WorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int
    request_id: str = Field(min_length=1, max_length=255)
    component: str = Field(min_length=1, max_length=23 * 1024 * 1024)
    export_name: str = Field(min_length=1, max_length=128)
    fuel: int = Field(gt=0, le=100_000_000)
    memory_bytes: int = Field(gt=0, le=512 * 1024 * 1024)


def _safe_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    sanitized = "".join(character if character.isprintable() else "?" for character in message)
    return sanitized[:1024] or exc.__class__.__name__


def run_worker(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    line = stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
    if not line or len(line) > MAX_REQUEST_BYTES:
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "success": False,
            "error": "invalid request size",
        }
    else:
        request_id = "unknown"
        try:
            request = WorkerRequest.model_validate_json(line)
            request_id = request.request_id
            if request.protocol_version != PROTOCOL_VERSION:
                raise ValueError("Unsupported worker protocol version.")
            component = base64.b64decode(request.component, validate=True)
            WasmtimeSandbox(
                SandboxLimits(fuel=request.fuel, memory_bytes=request.memory_bytes)
            ).invoke(component, request.export_name)
            response = {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "success": True,
                "error": None,
            }
        except Exception as exc:
            response = {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "success": False,
                "error": _safe_message(exc),
            }
    stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    stdout.flush()
    return 0 if response["success"] else 1


if __name__ == "__main__":
    raise SystemExit(run_worker())
