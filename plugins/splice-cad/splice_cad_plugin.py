"""Splice CAD-specific analysis provider for the OpenPDM Extension API v1."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import wit_world

MAX_CONTENT_BYTES = 5 * 1024 * 1024
SUPPORTED_SCHEMA_VERSION = 3
SUPPORTED_SPLICE_KIND = "project"
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


class PluginFailure(ValueError):
    """A deterministic, safe-to-return provider failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BomEntry:
    """One bounded Splice CAD bill-of-materials entry."""

    entry_id: str
    label: str
    mpn: str
    manufacturer: str
    part_type: str
    source_part_id: str | None


@dataclass(frozen=True)
class SplicePlan:
    """The bounded Splice CAD facts this plugin contributes to OpenPDM."""

    node_count: int
    link_count: int
    conductor_count: int
    conductor_splice_count: int
    mate_count: int
    bom_entries: tuple[BomEntry, ...]


def parse_spliceproject(content: bytes) -> SplicePlan:
    """Parse the bounded native Splice CAD project document (plain JSON)."""

    if len(content) > MAX_CONTENT_BYTES:
        raise PluginFailure(
            "splicecad.content_too_large", "Splice CAD content exceeds the 5 MiB limit."
        )
    try:
        document = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PluginFailure(
            "splicecad.invalid_document", "A Splice CAD project must be valid JSON."
        ) from exc
    if not isinstance(document, dict):
        raise PluginFailure(
            "splicecad.invalid_document", "A Splice CAD project must be a JSON object."
        )

    if document.get("splice_kind") != SUPPORTED_SPLICE_KIND:
        raise PluginFailure("splicecad.unsupported_kind", "A Splice CAD project file is required.")
    schema_version = document.get("schemaVersion")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise PluginFailure(
            "splicecad.unsupported_schema", "The Splice CAD schema version is missing."
        )
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise PluginFailure(
            "splicecad.unsupported_schema",
            f"Unsupported Splice CAD schema version {schema_version}.",
        )

    nodes = _require_collection(document, "nodes")
    links = _require_collection(document, "links")
    conductors = _require_collection(document, "conductors")
    conductor_splices = _require_collection(document, "conductorSplices")
    mates = _require_collection(document, "mates")
    bom = document.get("bom")
    if not isinstance(bom, list):
        raise PluginFailure(
            "splicecad.invalid_document", "The Splice CAD project is missing required data."
        )

    return SplicePlan(
        node_count=len(nodes),
        link_count=len(links),
        conductor_count=len(conductors),
        conductor_splice_count=len(conductor_splices),
        mate_count=len(mates),
        bom_entries=_read_bom_entries(bom),
    )


def _require_collection(
    document: dict[str, object], key: str
) -> "list[object] | dict[str, object]":
    value = document.get(key)
    if not isinstance(value, list | dict):
        raise PluginFailure(
            "splicecad.invalid_document", "The Splice CAD project is missing required data."
        )
    return value


def _read_bom_entries(bom: list[object]) -> tuple[BomEntry, ...]:
    entries: list[BomEntry] = []
    for raw in bom:
        if not isinstance(raw, dict):
            raise PluginFailure(
                "splicecad.invalid_document", "A Splice CAD BOM entry must be an object."
            )
        entry_id = raw.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            raise PluginFailure(
                "splicecad.invalid_document", "A Splice CAD BOM entry requires an id."
            )
        description = _text(raw.get("description"))
        mpn = _text(raw.get("mpn"))
        source_part_id = raw.get("sourcePartId")
        entries.append(
            BomEntry(
                entry_id=entry_id,
                label=description or mpn or entry_id,
                mpn=mpn,
                manufacturer=_text(raw.get("manufacturer")),
                part_type=_text(raw.get("type")),
                source_part_id=(
                    source_part_id
                    if isinstance(source_part_id, str)
                    and source_part_id
                    and source_part_id != _ZERO_UUID
                    else None
                ),
            )
        )
    return tuple(sorted(entries, key=lambda entry: (entry.label, entry.entry_id)))


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _success_response(
    *,
    analysis_metadata: list[dict[str, object]] | None = None,
    references: list[dict[str, object]] | None = None,
    relationships: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "success": True,
            "metadata": [],
            "analysis_metadata": analysis_metadata or [],
            "references": references or [],
            "relationships": relationships or [],
            "commands": [],
            "option_sets": [],
            "error": None,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _failure_response(failure: PluginFailure) -> str:
    return json.dumps(
        {
            "success": False,
            "metadata": [],
            "analysis_metadata": [],
            "references": [],
            "relationships": [],
            "commands": [],
            "option_sets": [],
            "error": {"code": failure.code, "message": failure.message, "retryable": False},
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def analyze(payload: dict[str, object]) -> str:
    """Produce deterministic generic contributions from one authorized project file."""

    try:
        analysis_input = payload["analysis_input"]
        if not isinstance(analysis_input, dict):
            raise PluginFailure("splicecad.invalid_request", "analysis_input is required.")
        content_base64 = analysis_input.get("content_base64")
        asset_id = analysis_input.get("asset_id")
        checksum = analysis_input.get("checksum_sha256")
        if not all(isinstance(value, str) for value in (content_base64, asset_id, checksum)):
            raise PluginFailure("splicecad.invalid_request", "The analysis input is incomplete.")
        content = base64.b64decode(content_base64, validate=True)
    except (KeyError, ValueError) as exc:
        if isinstance(exc, PluginFailure):
            return _failure_response(exc)
        return _failure_response(
            PluginFailure("splicecad.invalid_request", "Invalid base64 content.")
        )

    try:
        plan = parse_spliceproject(content)
    except PluginFailure as failure:
        return _failure_response(failure)

    metadata = [
        _metadata_entry(asset_id, "plan.node_count", "splicecad.plan.node_count", plan.node_count),
        _metadata_entry(asset_id, "plan.link_count", "splicecad.plan.link_count", plan.link_count),
        _metadata_entry(
            asset_id,
            "plan.conductor_count",
            "splicecad.plan.conductor_count",
            plan.conductor_count,
        ),
        _metadata_entry(
            asset_id,
            "plan.conductor_splice_count",
            "splicecad.plan.conductor_splice_count",
            plan.conductor_splice_count,
        ),
        _metadata_entry(asset_id, "plan.mate_count", "splicecad.plan.mate_count", plan.mate_count),
        _metadata_entry(
            asset_id, "plan.bom_count", "splicecad.plan.bom_count", len(plan.bom_entries)
        ),
    ]

    mappings = payload.get("relationship_mappings", {})
    if not isinstance(mappings, dict):
        return _failure_response(
            PluginFailure("splicecad.invalid_request", "relationship_mappings must be an object.")
        )

    references: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    for entry in plan.bom_entries:
        contribution_key = f"bom.{entry.entry_id}"
        entry_metadata = _bom_metadata(entry)
        target_asset_id = mappings.get(contribution_key)
        if isinstance(target_asset_id, str):
            relationships.append(
                {
                    "contribution_key": contribution_key,
                    "source_asset_id": asset_id,
                    "target_asset_id": target_asset_id,
                    "relationship_type": "depends_on",
                    "metadata": entry_metadata,
                }
            )
        else:
            references.append(
                {
                    "contribution_key": contribution_key,
                    "source_asset_id": asset_id,
                    "reference_type": "splicecad.bom_entry",
                    "target_uri": f"splicecad://project/{checksum}/bom/{entry.entry_id}",
                    "label": entry.label,
                    "metadata": entry_metadata,
                }
            )
    return _success_response(
        analysis_metadata=metadata, references=references, relationships=relationships
    )


def _metadata_entry(
    asset_id: str, contribution_key: str, key: str, value: int
) -> dict[str, object]:
    return {
        "contribution_key": contribution_key,
        "target_type": "asset",
        "target_id": asset_id,
        "key": key,
        "value": value,
        "value_type": "number",
    }


def _bom_metadata(entry: BomEntry) -> dict[str, str]:
    metadata = {"splicecad.bom_entry_id": entry.entry_id}
    if entry.mpn:
        metadata["splicecad.mpn"] = entry.mpn
    if entry.manufacturer:
        metadata["splicecad.manufacturer"] = entry.manufacturer
    if entry.part_type:
        metadata["splicecad.type"] = entry.part_type
    if entry.source_part_id is not None:
        metadata["splicecad.source_part_id"] = entry.source_part_id
    return metadata


try:
    import wit_world
except ImportError:
    wit_world = None


if wit_world is not None:

    class WitWorld(wit_world.WitWorld):
        """WebAssembly Component entry point generated from Extension API WIT."""

        def activate(self) -> None:
            return None

        def invoke(self, request: str) -> str:
            try:
                envelope = json.loads(request)
                if envelope.get("operation") != "analysis":
                    return _failure_response(
                        PluginFailure(
                            "unsupported_operation", "The requested operation is not supported."
                        )
                    )
                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    return _failure_response(
                        PluginFailure("splicecad.invalid_request", "Payload is required.")
                    )
                return analyze(payload)
            except json.JSONDecodeError:
                return _failure_response(
                    PluginFailure("splicecad.invalid_request", "Invalid JSON request.")
                )
