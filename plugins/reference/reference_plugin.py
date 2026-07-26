"""Domain-neutral Official Plugin proving the public Extension API v1 contract."""

import json
import json.decoder
import json.encoder
import json.scanner

import wit_world

_PRELOADED_JSON = json.dumps(json.loads("{}"))


def response(*, metadata: list[dict[str, object]] | None = None, commands: list[dict[str, object]] | None = None) -> str:
    return json.dumps(
        {
            "success": True,
            "metadata": metadata or [],
            "commands": commands or [],
            "error": None,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class WitWorld(wit_world.WitWorld):
    def activate(self) -> None:
        return None

    def invoke(self, request: str) -> str:
        envelope = json.loads(request)
        operation = envelope["operation"]
        context = envelope["context"]
        payload = envelope["payload"]
        configuration = envelope.get("configuration", {})
        metadata_key = configuration.get("metadata_key", "reference.processed")

        if operation == "metadata":
            return response(
                metadata=[
                    {
                        "target_type": payload["target_type"],
                        "target_id": payload["target_id"],
                        "key": metadata_key,
                        "value": "processed",
                        "value_type": "string",
                    }
                ]
            )
        if operation == "event":
            return response()
        if operation == "asset":
            return response(
                commands=[
                    {
                        "operation": "create_asset",
                        "context": context,
                        "payload": {
                            "project_id": context["project_id"],
                            "name": payload["name"],
                            "description": payload.get("description", ""),
                        },
                    }
                ]
            )
        return json.dumps(
            {
                "success": False,
                "metadata": [],
                "commands": [],
                "error": {
                    "code": "unsupported_operation",
                    "message": "The requested operation is not supported.",
                    "retryable": False,
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )
