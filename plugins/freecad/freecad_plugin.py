"""FreeCAD-specific analysis provider for the OpenPDM Extension API v1."""

from __future__ import annotations

import base64
import encodings.cp437
import json
import pyexpat
import zlib
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING
from xml.etree import ElementTree
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile

if TYPE_CHECKING:
    import wit_world

MAX_CONTENT_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_XML_BYTES = 5 * 1024 * 1024
_PRELOADED_ZLIB = zlib
_PRELOADED_EXPAT = expat
_PRELOADED_PYEXPAT = pyexpat
_PRELOADED_CP437 = encodings.cp437


class PluginFailure(ValueError):
    """A deterministic, safe-to-return provider failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FreecadDocument:
    """The bounded FreeCAD facts this plugin contributes to OpenPDM."""

    label: str
    object_count: int
    links: tuple[str, ...]


def parse_fcstd(content: bytes) -> FreecadDocument:
    """Parse the required XML member from a bounded FreeCAD document archive."""

    if len(content) > MAX_CONTENT_BYTES:
        raise PluginFailure("freecad.content_too_large", "FreeCAD content exceeds the 5 MiB limit.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if "Document.xml" not in archive.namelist():
                raise PluginFailure("freecad.invalid_archive", "Document.xml is required.")
            document_xml = archive.getinfo("Document.xml")
            if document_xml.file_size > MAX_DOCUMENT_XML_BYTES:
                raise PluginFailure(
                    "freecad.invalid_archive", "Document.xml exceeds the uncompressed size limit."
                )
            root = ElementTree.fromstring(archive.read("Document.xml"))
    except BadZipFile as exc:
        raise PluginFailure(
            "freecad.invalid_archive", "A FreeCAD document must be a ZIP archive."
        ) from exc
    except ElementTree.ParseError as exc:
        raise PluginFailure(
            "freecad.invalid_archive", "Document.xml must contain valid XML."
        ) from exc

    return FreecadDocument(
        label=_read_document_label(root),
        object_count=_read_object_count(root),
        links=tuple(sorted(_read_document_links(root))),
    )


def _read_document_label(root: ElementTree.Element) -> str:
    label = root.find("./Properties/Property[@name='Label']/String")
    value = label.get("value") if label is not None else None
    if not value:
        raise PluginFailure("freecad.invalid_document", "The document label is required.")
    return value


def _read_object_count(root: ElementTree.Element) -> int:
    objects = root.find("./Objects")
    count = objects.get("Count") if objects is not None else None
    try:
        return int(count) if count is not None else -1
    except ValueError as exc:
        raise PluginFailure(
            "freecad.invalid_document", "The document object count is invalid."
        ) from exc


def _read_document_links(root: ElementTree.Element) -> list[str]:
    return [
        name
        for object_node in root.findall("./Objects/Object")
        if object_node.get("type") == "App::Link"
        if (name := object_node.get("name"))
    ]


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
    """Produce deterministic generic contributions from one authorized document."""

    try:
        analysis_input = payload["analysis_input"]
        if not isinstance(analysis_input, dict):
            raise PluginFailure("freecad.invalid_request", "analysis_input is required.")
        content_base64 = analysis_input.get("content_base64")
        asset_id = analysis_input.get("asset_id")
        checksum = analysis_input.get("checksum_sha256")
        if not all(isinstance(value, str) for value in (content_base64, asset_id, checksum)):
            raise PluginFailure("freecad.invalid_request", "The analysis input is incomplete.")
        content = base64.b64decode(content_base64, validate=True)
    except (KeyError, ValueError) as exc:
        if isinstance(exc, PluginFailure):
            return _failure_response(exc)
        return _failure_response(
            PluginFailure("freecad.invalid_request", "Invalid base64 content.")
        )

    try:
        document = parse_fcstd(content)
    except PluginFailure as failure:
        return _failure_response(failure)

    metadata = [
        {
            "contribution_key": "document.label",
            "target_type": "asset",
            "target_id": asset_id,
            "key": "freecad.document.label",
            "value": document.label,
            "value_type": "string",
        },
        {
            "contribution_key": "document.object_count",
            "target_type": "asset",
            "target_id": asset_id,
            "key": "freecad.document.object_count",
            "value": document.object_count,
            "value_type": "number",
        },
        {
            "contribution_key": "document.link_count",
            "target_type": "asset",
            "target_id": asset_id,
            "key": "freecad.document.link_count",
            "value": len(document.links),
            "value_type": "number",
        },
    ]
    mappings = payload.get("relationship_mappings", {})
    if not isinstance(mappings, dict):
        return _failure_response(
            PluginFailure("freecad.invalid_request", "relationship_mappings must be an object.")
        )

    references: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    for link in document.links:
        contribution_key = f"document.link.{link}"
        target_asset_id = mappings.get(contribution_key)
        if isinstance(target_asset_id, str):
            relationships.append(
                {
                    "contribution_key": contribution_key,
                    "source_asset_id": asset_id,
                    "target_asset_id": target_asset_id,
                    "relationship_type": "depends_on",
                    "metadata": {"freecad.link_name": link},
                }
            )
        else:
            references.append(
                {
                    "contribution_key": contribution_key,
                    "source_asset_id": asset_id,
                    "reference_type": "freecad.document_link",
                    "target_uri": f"freecad://document/{checksum}/object/{link}",
                    "label": link,
                    "metadata": {"freecad.link_name": link},
                }
            )
    return _success_response(
        analysis_metadata=metadata, references=references, relationships=relationships
    )


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
                        PluginFailure("freecad.invalid_request", "Payload is required.")
                    )
                return analyze(payload)
            except json.JSONDecodeError:
                return _failure_response(
                    PluginFailure("freecad.invalid_request", "Invalid JSON request.")
                )
