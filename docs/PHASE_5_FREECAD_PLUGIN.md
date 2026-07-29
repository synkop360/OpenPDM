# Phase 5 FreeCAD Official Plugin

The first Phase 5 vertical slice installs the `org.openpdm.freecad` Official
Plugin through the public plugin administration API. It analyzes one authorized,
stored `.FCStd` Representation through the generic analysis-provider endpoint
and persists generic Metadata, References, and explicitly mapped Asset
Relationships. The Platform Core and generic Web UI do not define FreeCAD
objects, assemblies, or lifecycle behavior.

The plugin parses `Document.xml` from the `.FCStd` ZIP archive with only Python
standard-library archive and XML parsing. It does not import FreeCAD, run
FreeCADCmd, launch an executable, access storage, inspect a local document path,
modify a file, or synchronize with a desktop client. This is a stored-file
analysis capability, not a CAD launch or desktop-integration feature.

## Build And Install

Build the immutable plugin package from the repository root:

```powershell
uv run python scripts/build_freecad_plugin.py --output plugins/freecad/dist/freecad.openpdm-plugin
```

The build invokes `componentize-py` to compile the plugin into a WebAssembly
Component and validates the OpenPDM package. It does not start FreeCAD or an
external analysis program.

A Platform Administrator installs the resulting
`plugins/freecad/dist/freecad.openpdm-plugin` through Plugin Administration as
an `official` package, then enables it. The same workflow is available through
the public lifecycle API:

```text
POST /plugins/packages?plugin_type=official
POST /plugins/org.openpdm.freecad/state {"enabled": true}
GET  /providers
```

After enablement, `GET /providers` reports `org.openpdm.freecad` with the
`analysis_provider` capability. Disabling or removing the plugin follows the
ordinary plugin lifecycle and removes its analysis action from provider
discovery; it does not delete records already contributed by a prior analysis.

## User Workflow

1. Create an Engineering Asset, Revision, and Blob-backed Representation for a
   `.FCStd` document in an accessible Project.
2. In the generic Web UI, select that Representation in the discovered provider
   action and choose `Analyze representation`. The Web UI does not name a CAD
   program, upload a local program, offer a launch command, or submit
   `relationship_mappings`. This Web UI path is intentionally unmapped, so
   document links are retained as References rather than Asset Graph
   relationships.
3. Inspect the returned generic metadata and References in the existing
   Engineering Asset panels. The Asset Graph remains unchanged by this
   unmapped Web UI invocation.

An API client may request a generic Asset Graph relationship by explicitly
mapping a plugin dependency key to an existing accessible Engineering Asset in
the same Project. Mapping is API-only in this vertical slice; the generic Web
UI intentionally has no dependency-mapping control.

For example, an API client can invoke the operation with one explicit mapping:

```json
POST /plugins/org.openpdm.freecad/providers/analysis
{
  "representation_id": "representation-id",
  "project_id": "project-id",
  "organization_id": "organization-id",
  "relationship_mappings": {
    "document.link.Base": "target-asset-id"
  }
}
```

The generic route contract, authorization rules, and error responses are in
[API Reference](API_REFERENCE.md#analysis-providers).

## Plugin Contributions

For each supported document, the plugin contributes these plugin-owned metadata
keys:

* `freecad.document.label`
* `freecad.document.object_count`
* `freecad.document.link_count`

Each unmapped `App::Link` becomes a plugin-owned `freecad://` Reference. A link
becomes a generic `depends_on` Relationship only when the caller explicitly maps
its stable contribution key (`document.link.<link-name>`) to an existing,
authorized Engineering Asset. The Platform Core does not interpret FreeCAD
object types, metadata keys, reference URIs, or the relationship choice.

## Fixtures And Provenance

`plugins/freecad/fixtures.json` records SHA-256 digests for the immutable
`.FCStd` files copied from `C:\Program Files\FreeCAD 1.0\data\examples`; their
repository provenance is also recorded in [the sample README](../sample/freecad/README.md).
Parser tests use `AssemblyExample.FCStd`, whose expected document label is
`AssemblyExample`, object count is 53, and document-link count is 13.

The source installation's `doc/LICENSE.html` identifies the FreeCAD application
as LGPL 2 or later. The copied example documents did not carry an individual
license notice in that installation. OpenPDM preserves their origin and hashes
but makes no independent license assertion for the documents; anyone
redistributing them must review the applicable upstream FreeCAD example-data
terms before doing so.

## Supported And Unsupported Scope

Supported in this prototype slice:

* bounded analysis of stored `.FCStd` documents no larger than 5 MiB;
* document label, object count, and `App::Link` count contributions;
* generic Web UI analysis with no mappings, preserving document links as
  plugin-owned References;
* API-only explicit mapping of document links as generic `depends_on`
  relationships;
* repeated analysis without duplicate contributions.

Not supported:

* STEP parsing, import, export, conversion, or regeneration;
* BOM extraction, geometry inspection, previews, or broad native-property
  coverage;
* document or Blob mutation by the plugin;
* desktop synchronization, desktop commands, or opening a document in FreeCAD;
* launching FreeCAD, FreeCADCmd, or any other executable from the Web UI,
  backend, plugin runtime, or tests.

Malformed archives and unsupported content produce bounded provider diagnostics.
The server rejects a Representation above the 5 MiB decoded-content limit with
`413` before the plugin is invoked. The distinct analysis-provider sandbox fuel
budget in ADR-0049 remains bounded and does not change the content limit,
memory limit, deadline, or denied ambient capabilities.

## Evidence And Decisions

The package-to-analysis public journey is covered by
`backend/tests/test_freecad_plugin_e2e.py`; parser and malformed-input coverage
is in `plugins/freecad/tests/test_parser.py`. The generic route and
authorization coverage is in `backend/tests/test_analysis_provider_api.py`.
This slice follows [ADR-0047](adr/ADR-0047%20-%20Authorize%20Bounded%20Representation%20Analysis%20Inputs.md),
[ADR-0048](adr/ADR-0048%20-%20Accept%20Provider%20Analysis%20Contributions.md),
and [ADR-0049](adr/ADR-0049%20-%20Set%20Analysis%20Provider%20Sandbox%20Fuel%20Budget.md).

## Phase 5 Acceptance Matrix

Automated evidence was recorded on 2026-07-29. The local-service smoke check
remains pending maintainer execution; no manual result is inferred from the
automated checks.

| Scenario | Evidence | Status |
| --- | --- | --- |
| Valid `.FCStd` | `backend/tests/test_freecad_plugin_e2e.py::test_freecad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Malformed archive | `plugins/freecad/tests/test_parser.py::test_parser_rejects_non_zip_payload` and `test_parser_rejects_archive_without_document_xml` | Passed |
| Unsupported STEP | Manual local-service smoke check below; STEP is outside the supported scope | Pending |
| Oversized content | `plugins/freecad/tests/test_parser.py::test_parser_rejects_content_larger_than_declared_limit` and `backend/tests/test_analysis_provider_api.py::test_analysis_input_rejects_content_above_configured_limit` | Passed |
| No Blob | `backend/tests/test_analysis_provider_api.py::test_analysis_input_rejects_representation_without_blob` | Passed |
| Unauthorized actor | `backend/tests/test_analysis_provider_api.py::test_analysis_input_requires_read_access_and_representation_blob` | Passed |
| Unmapped link | `backend/tests/test_freecad_plugin_e2e.py::test_freecad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Explicitly mapped link | `backend/tests/test_freecad_plugin_e2e.py::test_freecad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Repeated analysis | `backend/tests/test_freecad_plugin_e2e.py::test_freecad_official_plugin_exercises_the_public_analysis_journey` | Passed |
| Disabled plugin | Manual local-service smoke check below | Pending |
| Existing-provider regression | `backend/tests/test_reference_plugin_e2e.py::test_reference_official_plugin_exercises_phase4_journey` and `backend/tests/test_dummy_categories_plugin_e2e.py::test_dummy_categories_plugin_exercises_public_extension_api` | Passed |

### Automated Gate Results

* Rebuilt and validated `plugins/freecad/dist/freecad.openpdm-plugin` with
  `uv run python scripts/build_freecad_plugin.py --output plugins/freecad/dist/freecad.openpdm-plugin`: passed.
* Focused plugin, API, and existing-provider coverage:
  `uv run pytest plugins/freecad/tests/test_parser.py backend/tests/test_freecad_plugin_e2e.py backend/tests/test_analysis_provider_api.py backend/tests/test_reference_plugin_e2e.py backend/tests/test_dummy_categories_plugin_e2e.py -v`: 26 passed.
* `pnpm.cmd --dir frontend lint`: passed.
* `pnpm.cmd --dir frontend test -- --run`: 54 passed.
* `pnpm.cmd --dir frontend build`: passed.
* `pnpm.cmd --dir frontend exec playwright test --project=chromium-desktop`: 7 passed. The plan's `chromium` project name is not configured; the configured desktop Chromium project was used after the exact command reported that mismatch.
* `uv run python scripts/validate_documentation.py`,
  `uv run python .github/automation/project/validate.py .github/automation/project/project.yaml`,
  and `git diff --check`: passed.

The full backend suite is not yet green: `uv run pytest backend/tests -v`
reported 104 passed, 4 skipped, and 2 failures. Both failures are older
migration-upgrade tests (`test_upload_session_migration_is_upgradeable` and
`test_project_asset_view_migration_is_upgradeable`) that attempt to add the
already-present `analysis_contribution_id` column. The focused analysis
migration check passes. `uv run ruff format --check backend tests plugins
scripts` also reports three formatting candidates, including generated
reference-plugin code; `uv run ruff check backend tests plugins scripts`
reports 94 findings in generated plugin bindings. These repository-wide gates
must be resolved before declaring the Phase 5 acceptance gate fully passed.

### Pending Manual Local-Service Smoke Check

Run the documented local services, then, as a Platform Administrator, build,
install, and enable `plugins/freecad/dist/freecad.openpdm-plugin`. Upload
`AssemblyExample.FCStd` to a Blob-backed Representation in an accessible
Project. In the generic Web UI, select the Representation and run `Analyze
representation`; verify the three `freecad.document.*` metadata entries and
13 References. Then use the public analysis endpoint once with
`document.link.Base` explicitly mapped to an accessible Engineering Asset and
verify one `depends_on` Relationship, the timeline event, and audit record.
Disable the plugin and verify the analysis action disappears while prior
records remain. Confirm during this sequence that no external executable or
CAD process starts. Record the operator, date, and outcome here before
changing this status from Pending.
