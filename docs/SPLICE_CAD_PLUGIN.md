# Splice CAD Official Plugin

This vertical slice installs the `org.openpdm.splice-cad` Official Plugin through
the public plugin administration API. It analyzes one authorized, stored
`.spliceproject` Representation through the generic analysis-provider endpoint
and persists generic Metadata, References, and explicitly mapped Asset
Relationships. It mirrors the `org.openpdm.freecad` slice
([Phase 5 FreeCAD Official Plugin](PHASE_5_FREECAD_PLUGIN.md)) for Splice CAD
wiring-harness projects. The Platform Core and generic Web UI do not define
Splice CAD nodes, conductors, splices, or harness semantics.

The plugin parses the native `.spliceproject` document with only the Python
standard library (`json.loads`). It does not call the Splice CAD API or desktop
bridge, import a Splice CAD library, launch an executable, access storage,
inspect a local document path, modify a file, or synchronize with a desktop
client. This is a stored-file analysis capability, not a CAD launch or
desktop-integration feature.

## Build And Install

Build the immutable plugin package from the repository root:

```powershell
uv run python scripts/build_splice_cad_plugin.py --output plugins/splice-cad/dist/splice-cad.openpdm-plugin
```

The build invokes `componentize-py` to compile the plugin into a WebAssembly
Component and validates the OpenPDM package. It does not start Splice CAD or an
external analysis program.

A Platform Administrator installs the resulting
`plugins/splice-cad/dist/splice-cad.openpdm-plugin` through Plugin
Administration as an `official` package, then enables it. The same workflow is
available through the public lifecycle API:

```text
POST /plugins/packages?plugin_type=official
POST /plugins/org.openpdm.splice-cad/state {"enabled": true}
GET  /providers
```

After enablement, `GET /providers` reports `org.openpdm.splice-cad` with the
`analysis_provider` capability. Disabling or removing the plugin follows the
ordinary plugin lifecycle and removes its analysis action from provider
discovery; it does not delete records already contributed by a prior analysis.

## User Workflow

1. In Splice CAD desktop, use the native **Save As** button to write the
   project to a `.spliceproject` file. `.spliceproject` is plain JSON produced
   entirely by the desktop application — there is no OpenPDM bridge, API call,
   or separate export step. Getting the file out of Splice CAD and into OpenPDM
   is a manual user action, not part of the plugin.
2. Create an Engineering Asset, Revision, and Blob-backed Representation for the
   `.spliceproject` file in an accessible Project, uploading it through the
   ordinary Blob upload path.
3. In the generic Web UI, select that Representation in the discovered provider
   action and choose `Analyze representation`. The Web UI does not name Splice
   CAD, upload a program, offer a launch command, or submit
   `relationship_mappings`. This Web UI path is intentionally unmapped, so BOM
   entries are retained as References rather than Asset Graph relationships.
4. Inspect the returned generic metadata and References in the existing
   Engineering Asset panels. The Asset Graph remains unchanged by this unmapped
   Web UI invocation.

An API client may request a generic Asset Graph relationship by explicitly
mapping a plugin dependency key to an existing accessible Engineering Asset in
the same Project. Mapping is API-only in this vertical slice; the generic Web UI
intentionally has no dependency-mapping control.

```json
POST /plugins/org.openpdm.splice-cad/providers/analysis
{
  "representation_id": "representation-id",
  "project_id": "project-id",
  "organization_id": "organization-id",
  "relationship_mappings": {
    "bom.<bom-entry-id>": "target-asset-id"
  }
}
```

The generic route contract, authorization rules, and error responses are in
[API Reference](API_REFERENCE.md#analysis-providers).

## Plugin Contributions

Before parsing, the plugin confirms the document is a JSON object whose
`splice_kind` is `project` and whose `schemaVersion` is `3` — the same role as
confirming a `.FCStd` is a ZIP archive containing `Document.xml`.

For each supported project, the plugin contributes these plugin-owned metadata
keys (all targeting the analyzed Engineering Asset):

* `splicecad.plan.node_count`
* `splicecad.plan.link_count`
* `splicecad.plan.conductor_count`
* `splicecad.plan.conductor_splice_count`
* `splicecad.plan.mate_count`
* `splicecad.plan.bom_count`

Each `bom` entry becomes a plugin-owned `splicecad://` Reference with the stable
contribution key `bom.<bom-entry-id>`. A BOM entry becomes a generic
`depends_on` Relationship only when the caller explicitly maps that contribution
key to an existing, authorized Engineering Asset in the same Project. Mapping is
per BOM part, not per node placement: multiple nodes that share a `bomEntryId`
collapse to one contribution.

`bom[].sourcePartId` points into the source account's private Splice CAD part
library, not into OpenPDM. When it is present and not the zero UUID it is
carried only as opaque descriptive metadata (`splicecad.source_part_id`) on the
contribution; it is never emitted as a Reference URI or used as a relationship
target. The Platform Core does not interpret Splice CAD node types, metadata
keys, reference URIs, or the relationship choice.

## Fixtures And Provenance

`plugins/splice-cad/fixtures.json` records the SHA-256 digest and deterministic
structural facts for `sample/splice-cad/native/SampleHarness.spliceproject`.
That file is the maintainer's own real wiring-harness project, saved with Splice
CAD desktop's native Save As and anonymized before commit: all human-authored
free text is replaced with generic placeholders and every `bom[].sourcePartId`
UUID is zeroed, while every id, position, pin count, wire gauge/color, net name,
and structural relationship is preserved unchanged. Its provenance and
anonymization are documented in
[the sample README](../sample/splice-cad/README.md).

Parser tests use `SampleHarness.spliceproject`, whose deterministic facts are:
`schemaVersion` 3, `splice_kind` `project`, 47 nodes, 50 links, 52 conductors,
9 conductor splices, 12 mates, and 21 BOM entries.

## Supported And Unsupported Scope

Supported in this prototype slice:

* bounded analysis of stored `.spliceproject` documents no larger than 5 MiB;
* node, link, conductor, conductor-splice, mate, and BOM count contributions;
* generic Web UI analysis with no mappings, preserving BOM entries as
  plugin-owned References;
* API-only explicit mapping of BOM entries as generic `depends_on`
  relationships;
* repeated analysis without duplicate contributions.

Not supported:

* live Splice CAD API, desktop-bridge, or MCP calls; write-back to Splice CAD;
* geometry, cable length, routing, or schematic-page rendering;
* structural contribution of `conductorSplices` or `mates` topology — only their
  counts are contributed; the join topology has no cross-Asset meaning in this
  slice and is deferred;
* parsing `pages`, `pageOrder`, `nodePagePositions`, `nodePageSizes`,
  `nodePageAssignments`, `linkPageAssignments`, `viewState`, or `images` —
  presentational/layout data only, ignored the same way the FreeCAD plugin
  ignores GUI-only document data;
* parsing `assemblyRefs`, `assemblies`, `cables`, `signals`, `nets`,
  `deviceGroups`, `wireGroups`, `drcDismissals`, or `subassemblyInstances` —
  present in schema version 3 but empty on the only available fixture; no
  parsing logic is built for them without a second fixture that populates them;
* automatic relationship inference — mapping stays explicit and API-only, the
  same deferral as the FreeCAD slice;
* document or Blob mutation by the plugin;
* launching Splice CAD or any other executable from the Web UI, backend, plugin
  runtime, or tests.

Malformed JSON, a wrong `splice_kind`, an unsupported `schemaVersion`, and
missing required sections produce bounded provider diagnostics. The server
rejects a Representation above the 5 MiB decoded-content limit with `413` before
the plugin is invoked. The distinct analysis-provider sandbox fuel budget in
ADR-0049 remains bounded and does not change the content limit, memory limit,
deadline, or denied ambient capabilities.

## Evidence And Decisions

The package-to-analysis public journey is covered by
`backend/tests/test_splice_cad_plugin_e2e.py`; parser and malformed-input
coverage is in `plugins/splice-cad/tests/test_parser.py`. The generic route and
authorization coverage is shared with the FreeCAD slice in
`backend/tests/test_analysis_provider_api.py`. This slice follows
[ADR-0047](adr/ADR-0047%20-%20Authorize%20Bounded%20Representation%20Analysis%20Inputs.md),
[ADR-0048](adr/ADR-0048%20-%20Accept%20Provider%20Analysis%20Contributions.md),
and [ADR-0049](adr/ADR-0049%20-%20Set%20Analysis%20Provider%20Sandbox%20Fuel%20Budget.md);
it adds no new architectural decision.

## Acceptance Matrix

Automated evidence was recorded on 2026-08-28.

| Scenario | Evidence | Status |
| --- | --- | --- |
| Valid `.spliceproject` | `backend/tests/test_splice_cad_plugin_e2e.py::test_splice_cad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Malformed / non-JSON | `plugins/splice-cad/tests/test_parser.py::test_parser_rejects_non_json_payload` | Passed |
| Wrong `splice_kind` | `plugins/splice-cad/tests/test_parser.py::test_parser_rejects_wrong_splice_kind` and `test_analysis_rejects_a_wrong_kind_document_with_a_bounded_diagnostic` | Passed |
| Unsupported `schemaVersion` | `plugins/splice-cad/tests/test_parser.py::test_parser_rejects_unsupported_schema_version` | Passed |
| Missing required fields | `plugins/splice-cad/tests/test_parser.py::test_parser_rejects_missing_required_fields` | Passed |
| Oversized content | `plugins/splice-cad/tests/test_parser.py::test_parser_rejects_content_larger_than_declared_limit` and `backend/tests/test_analysis_provider_api.py::test_analysis_input_rejects_content_above_configured_limit` | Passed |
| No Blob | `backend/tests/test_analysis_provider_api.py::test_analysis_input_rejects_representation_without_blob` | Passed |
| Unauthorized actor | `backend/tests/test_analysis_provider_api.py::test_analysis_input_requires_read_access_and_representation_blob` | Passed |
| Unmapped BOM entry | `backend/tests/test_splice_cad_plugin_e2e.py::test_splice_cad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Explicitly mapped BOM entry | `backend/tests/test_splice_cad_plugin_e2e.py::test_splice_cad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Repeated analysis | `backend/tests/test_splice_cad_plugin_e2e.py::test_splice_cad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Built component invocation | `plugins/splice-cad/tests/test_parser.py::test_built_package_invocation_maps_relationship_by_contribution_key` | Passed |
| Existing-provider regression | `backend/tests/test_freecad_plugin_e2e.py`, `backend/tests/test_reference_plugin_e2e.py`, `backend/tests/test_dummy_categories_plugin_e2e.py` | Passed |

### Automated Gate Results

* Built and validated `plugins/splice-cad/dist/splice-cad.openpdm-plugin` with
  `uv run python scripts/build_splice_cad_plugin.py`: passed.
* Focused plugin and e2e coverage:
  `uv run pytest plugins/splice-cad/tests/test_parser.py backend/tests/test_splice_cad_plugin_e2e.py -v`: 11 passed.
* Full backend suite `uv run pytest`: see the commit / PR description for the run count.
* `uv run ruff check` and `uv run ruff format --check` on `plugins/splice-cad`,
  `scripts/build_splice_cad_plugin.py`, and `backend/tests/test_splice_cad_plugin_e2e.py`: passed.
* `uv run python scripts/validate_documentation.py`: passed.

A manual local-service smoke check against the running Compose stack has not yet
been recorded for this slice; the FreeCAD slice's smoke procedure in
[PHASE_5_FREECAD_PLUGIN.md](PHASE_5_FREECAD_PLUGIN.md) applies with
`.spliceproject` in place of `.FCStd` and `bom.<bom-entry-id>` in place of
`document.link.<link-name>`.
