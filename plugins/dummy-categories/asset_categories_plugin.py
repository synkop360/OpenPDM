"""Community Plugin fixture exercising generic Phase 4 Extension API capabilities."""

import json
import json.decoder
import json.encoder
import json.scanner

import wit_world

_PRELOADED_JSON = json.dumps(json.loads("{}"))


def response(
    *,
    metadata: list[dict[str, object]] | None = None,
    commands: list[dict[str, object]] | None = None,
    option_sets: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "success": True,
            "metadata": metadata or [],
            "commands": commands or [],
            "option_sets": option_sets or [],
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
        category = payload.get("category", configuration.get("default_category", "document"))

        if operation == "options":
            return response(
                option_sets=[
                    {
                        "key": "category",
                        "label": "Asset category",
                        "options": [
                            {"value": "document", "label": "Document"},
                            {"value": "drawing", "label": "Drawing"},
                            {"value": "model", "label": "3D model"},
                            {"value": "assembly", "label": "Assembly"},
                        ],
                    }
                ]
            )

        if operation == "metadata":
            return response(
                metadata=[
                    {
                        "target_type": payload["target_type"],
                        "target_id": payload["target_id"],
                        "key": "classification.category",
                        "value": category,
                        "value_type": "string",
                    },
                    {
                        "target_type": payload["target_type"],
                        "target_id": payload["target_id"],
                        "key": "classification.managed_by",
                        "value": "org.openpdm.examples.asset-categories",
                        "value_type": "string",
                    },
                ]
            )
        if operation == "asset":
            name_prefix = configuration.get("name_prefix", "Categorized")
            return response(
                commands=[
                    {
                        "operation": "create_asset",
                        "context": context,
                        "payload": {
                            "project_id": context["project_id"],
                            "name": f"{name_prefix}: {payload['name']}",
                            "description": payload.get(
                                "description", f"Asset prepared for category {category}"
                            ),
                        },
                    }
                ]
            )
        if operation == "event":
            return response()
        return json.dumps(
            {
                "success": False,
                "metadata": [],
                "commands": [],
                "option_sets": [],
                "error": {
                    "code": "unsupported_operation",
                    "message": "The requested operation is not supported.",
                    "retryable": False,
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )
