from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openpdm.extension_api import validate_plugin_package
from openpdm.plugin_runtime import WasmtimeWorkerSupervisor

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "sample" / "splice-cad" / "native"
SAMPLE_FIXTURE = FIXTURE_ROOT / "SampleHarness.spliceproject"

SPEC = importlib.util.spec_from_file_location(
    "splice_cad_plugin", PLUGIN_ROOT / "splice_cad_plugin.py"
)
assert SPEC is not None and SPEC.loader is not None
splice_cad_plugin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = splice_cad_plugin
SPEC.loader.exec_module(splice_cad_plugin)

BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_splice_cad_plugin", REPOSITORY_ROOT / "scripts" / "build_splice_cad_plugin.py"
)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
build_splice_cad_plugin = importlib.util.module_from_spec(BUILD_SPEC)
sys.modules[BUILD_SPEC.name] = build_splice_cad_plugin
BUILD_SPEC.loader.exec_module(build_splice_cad_plugin)

EXPECTED_METADATA_KEYS = [
    "splicecad.plan.node_count",
    "splicecad.plan.link_count",
    "splicecad.plan.conductor_count",
    "splicecad.plan.conductor_splice_count",
    "splicecad.plan.mate_count",
    "splicecad.plan.bom_count",
]


def fixture_manifest() -> dict[str, object]:
    return json.loads((PLUGIN_ROOT / "fixtures.json").read_text(encoding="utf-8"))


def test_fixture_manifest_hashes_match_immutable_native_documents() -> None:
    fixtures = fixture_manifest()["fixtures"]
    assert isinstance(fixtures, list)
    for fixture in fixtures:
        assert isinstance(fixture, dict)
        content = (FIXTURE_ROOT / fixture["filename"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == fixture["sha256"]


def test_sample_harness_fixture_has_documented_deterministic_facts() -> None:
    plan = splice_cad_plugin.parse_spliceproject(SAMPLE_FIXTURE.read_bytes())

    assert plan.node_count == 47
    assert plan.link_count == 50
    assert plan.conductor_count == 52
    assert plan.conductor_splice_count == 9
    assert plan.mate_count == 12
    assert len(plan.bom_entries) == 21
    assert list(plan.bom_entries) == sorted(
        plan.bom_entries, key=lambda entry: (entry.label, entry.entry_id)
    )


def test_parser_rejects_non_json_payload() -> None:
    with pytest.raises(splice_cad_plugin.PluginFailure, match="valid JSON"):
        splice_cad_plugin.parse_spliceproject(b"not json at all {")


def test_parser_rejects_wrong_splice_kind() -> None:
    content = json.dumps({"splice_kind": "harness", "schemaVersion": 3}).encode("utf-8")

    with pytest.raises(splice_cad_plugin.PluginFailure, match="project file is required"):
        splice_cad_plugin.parse_spliceproject(content)


def test_parser_rejects_unsupported_schema_version() -> None:
    content = json.dumps({"splice_kind": "project", "schemaVersion": 99}).encode("utf-8")

    with pytest.raises(splice_cad_plugin.PluginFailure, match="schema version"):
        splice_cad_plugin.parse_spliceproject(content)


def test_parser_rejects_missing_required_fields() -> None:
    content = json.dumps({"splice_kind": "project", "schemaVersion": 3}).encode("utf-8")

    with pytest.raises(splice_cad_plugin.PluginFailure, match="missing required data"):
        splice_cad_plugin.parse_spliceproject(content)


def test_parser_rejects_content_larger_than_declared_limit() -> None:
    with pytest.raises(splice_cad_plugin.PluginFailure, match="5 MiB"):
        splice_cad_plugin.parse_spliceproject(b"0" * (splice_cad_plugin.MAX_CONTENT_BYTES + 1))


def test_analysis_output_is_deterministic_and_respects_explicit_mappings() -> None:
    content = SAMPLE_FIXTURE.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    mapped_entry_id = splice_cad_plugin.parse_spliceproject(content).bom_entries[0].entry_id
    payload = {
        "analysis_input": {
            "asset_id": "source-asset",
            "checksum_sha256": checksum,
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
        "relationship_mappings": {f"bom.{mapped_entry_id}": "target-asset"},
    }

    first = json.loads(splice_cad_plugin.analyze(payload))
    second = json.loads(splice_cad_plugin.analyze(payload))

    assert first == second
    assert [entry["key"] for entry in first["analysis_metadata"]] == EXPECTED_METADATA_KEYS
    assert {entry["key"]: entry["value"] for entry in first["analysis_metadata"]} == {
        "splicecad.plan.node_count": 47,
        "splicecad.plan.link_count": 50,
        "splicecad.plan.conductor_count": 52,
        "splicecad.plan.conductor_splice_count": 9,
        "splicecad.plan.mate_count": 12,
        "splicecad.plan.bom_count": 21,
    }
    assert len(first["references"]) == 20
    assert first["references"] == sorted(first["references"], key=lambda entry: entry["label"])
    assert all(
        entry["target_uri"].startswith(f"splicecad://project/{checksum}/bom/")
        for entry in first["references"]
    )
    assert first["relationships"] == [
        {
            "contribution_key": f"bom.{mapped_entry_id}",
            "source_asset_id": "source-asset",
            "target_asset_id": "target-asset",
            "relationship_type": "depends_on",
            "metadata": first["relationships"][0]["metadata"],
        }
    ]
    assert first["relationships"][0]["metadata"]["splicecad.bom_entry_id"] == mapped_entry_id


def test_analysis_rejects_a_wrong_kind_document_with_a_bounded_diagnostic() -> None:
    payload = {
        "analysis_input": {
            "asset_id": "source-asset",
            "checksum_sha256": "0" * 64,
            "content_base64": base64.b64encode(b'{"splice_kind": "harness"}').decode("ascii"),
        }
    }

    response = json.loads(splice_cad_plugin.analyze(payload))

    assert response["success"] is False
    assert response["error"]["code"] == "splicecad.unsupported_kind"
    assert response["error"]["retryable"] is False


def test_built_package_invocation_maps_relationship_by_contribution_key() -> None:
    content = SAMPLE_FIXTURE.read_bytes()
    mapped_entry_id = splice_cad_plugin.parse_spliceproject(content).bom_entries[0].entry_id
    request = {
        "operation": "analysis",
        "context": {},
        "configuration": {},
        "payload": {
            "analysis_input": {
                "asset_id": "source-asset",
                "checksum_sha256": hashlib.sha256(content).hexdigest(),
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
            "relationship_mappings": {f"bom.{mapped_entry_id}": "target-asset"},
        },
    }
    with TemporaryDirectory() as temporary_directory:
        package_path = build_splice_cad_plugin.build(
            Path(temporary_directory) / "splice-cad.openpdm-plugin"
        )
        package = validate_plugin_package(package_path.read_bytes())

    result = WasmtimeWorkerSupervisor(timeout_seconds=10).invoke(
        package.component,
        export_name="invoke",
        arguments=[json.dumps(request, sort_keys=True, separators=(",", ":"))],
        fuel=200_000_000,
    )

    assert result.success, result.diagnostic_reason
    assert result.result is not None
    response = json.loads(result.result)
    assert response["success"] is True
    assert response["relationships"] == [
        {
            "contribution_key": f"bom.{mapped_entry_id}",
            "source_asset_id": "source-asset",
            "target_asset_id": "target-asset",
            "relationship_type": "depends_on",
            "metadata": response["relationships"][0]["metadata"],
        }
    ]
    assert len(response["references"]) == 20
