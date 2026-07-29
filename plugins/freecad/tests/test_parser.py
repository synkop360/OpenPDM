from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "sample" / "freecad" / "native"

SPEC = importlib.util.spec_from_file_location("freecad_plugin", PLUGIN_ROOT / "freecad_plugin.py")
assert SPEC is not None and SPEC.loader is not None
freecad_plugin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = freecad_plugin
SPEC.loader.exec_module(freecad_plugin)


def fixture_manifest() -> dict[str, object]:
    return json.loads((PLUGIN_ROOT / "fixtures.json").read_text(encoding="utf-8"))


def test_fixture_manifest_hashes_match_immutable_native_documents() -> None:
    fixtures = fixture_manifest()["fixtures"]
    assert isinstance(fixtures, list)
    for fixture in fixtures:
        assert isinstance(fixture, dict)
        content = (FIXTURE_ROOT / fixture["filename"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == fixture["sha256"]


def test_assembly_fixture_has_documented_deterministic_facts() -> None:
    document = freecad_plugin.parse_fcstd((FIXTURE_ROOT / "AssemblyExample.FCStd").read_bytes())

    assert document.label == "AssemblyExample"
    assert document.object_count == 53
    assert len(document.links) == 13
    assert document.links == tuple(sorted(document.links))


def test_parser_rejects_non_zip_payload() -> None:
    with pytest.raises(freecad_plugin.PluginFailure, match="ZIP archive"):
        freecad_plugin.parse_fcstd(b"not a zip archive")


def test_parser_rejects_archive_without_document_xml() -> None:
    content = _zip_content({"Other.xml": b"<Document />"})

    with pytest.raises(freecad_plugin.PluginFailure, match="Document.xml is required"):
        freecad_plugin.parse_fcstd(content)


def test_parser_rejects_content_larger_than_declared_limit() -> None:
    with pytest.raises(freecad_plugin.PluginFailure, match="5 MiB"):
        freecad_plugin.parse_fcstd(b"0" * (freecad_plugin.MAX_CONTENT_BYTES + 1))


def test_analysis_output_is_deterministic_and_respects_explicit_mappings() -> None:
    content = (FIXTURE_ROOT / "AssemblyExample.FCStd").read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    payload = {
        "analysis_input": {
            "asset_id": "source-asset",
            "checksum_sha256": checksum,
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
        "relationship_mappings": {"Base": "target-asset"},
    }

    first = json.loads(freecad_plugin.analyze(payload))
    second = json.loads(freecad_plugin.analyze(payload))

    assert first == second
    assert [entry["key"] for entry in first["analysis_metadata"]] == [
        "freecad.document.label",
        "freecad.document.object_count",
        "freecad.document.link_count",
    ]
    assert len(first["references"]) == 12
    assert first["references"] == sorted(first["references"], key=lambda entry: entry["label"])
    assert first["relationships"] == [
        {
            "contribution_key": "document.link.Base",
            "source_asset_id": "source-asset",
            "target_asset_id": "target-asset",
            "relationship_type": "depends_on",
            "metadata": {"freecad.link_name": "Base"},
        }
    ]


def _zip_content(members: dict[str, bytes]) -> bytes:
    from io import BytesIO
    from zipfile import ZipFile

    content = BytesIO()
    with ZipFile(content, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return content.getvalue()
