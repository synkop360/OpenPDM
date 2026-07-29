# FreeCAD Mechanical Official Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a FreeCAD Official Plugin that analyzes a stored `.FCStd` Representation in the WebAssembly sandbox and contributes only generic metadata, references, and explicitly mapped Asset relationships.

**Architecture:** The Platform Core receives two additive, domain-neutral Extension API v1 capabilities: bounded, authorized Representation analysis input and provider-owned analysis contributions. The FreeCAD Official Plugin contains the archive/XML parser, every `freecad.*` metadata key, the dependency interpretation, fixture expectations, and mapping lookup; owning Platform Modules only validate, authorize, persist, audit, and emit events for generic records.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic, WebAssembly Components through componentize-py and Wasmtime, React/TypeScript/Vite, Vitest, Playwright, pytest, Ruff.

## Global Constraints

* The Platform Core, Platform Modules, public application API, and generic Web UI must not define CAD types, assemblies, BOMs, FreeCAD properties, or vendor-specific lifecycle semantics.
* FreeCAD parsing and every `freecad.*` key, dependency identifier, reference URI, and relationship type selection belong exclusively to `plugins/freecad/`.
* Do not launch `FreeCAD`, `FreeCADCmd`, or any third-party executable from the Web UI, backend, plugin runtime, or tests. Desktop launch and synchronization are out of scope.
* Use Extension API v1 additively under ADR-0036; plugins receive no repository, database session, object-storage credential, package path, or Platform Module interface.
* Use public Platform Module interfaces and `MODULES` composition only. Do not bypass the Extension API or import another Platform Module implementation.
* A plugin may create a generic Asset relationship only from a caller-supplied mapping to an existing, authorized Engineering Asset. An unmapped dependency remains a generic Reference under ADR-0031.
* Bound decoded analysis content to 5 MiB. Reject a larger Representation before invoking the plugin with `413` and a stable problem detail. Never base64-decode unbounded client input.
* Preserve existing `asset_provider`, `metadata_provider`, `option_provider`, and `event_handler` behavior and public routes.
* Keep the fixture provenance in `sample/freecad/README.md`; use the copied `.FCStd` files without regenerating them through FreeCAD.

---

## Planned File Structure

| Path | Responsibility |
| --- | --- |
| `docs/adr/ADR-0047 - Authorize Bounded Representation Analysis Inputs.md` | Decision for generic, read-only analysis bytes and the 5 MiB boundary. |
| `docs/adr/ADR-0048 - Accept Provider Analysis Contributions.md` | Decision for generic metadata, Reference, and mapped Relationship contribution persistence. |
| `backend/src/openpdm/extension_api/contracts.py` | Add generic `analysis_provider` and its input/contribution Pydantic contracts. |
| `backend/src/openpdm/plugin_application.py` | Orchestrate authorized analysis invocation and contribution persistence through public interfaces. |
| `backend/src/openpdm/api/core.py` | Add the public analysis request/response models and route. |
| `backend/src/openpdm/infrastructure/settings.py` | Expose the bounded analysis-content setting with a 5 MiB default. |
| `frontend/src/api.ts` | Add typed analysis invocation client and result types. |
| `frontend/src/App.tsx` | Add a generic Representation-selection analysis action; no executable-launch path. |
| `plugins/freecad/` | Official Plugin manifest, sandboxed parser, fixture manifest, build configuration, and README. |
| `scripts/build_freecad_plugin.py` | Build and validate the reproducible FreeCAD plugin package. |
| `backend/tests/test_analysis_provider_api.py` | Contract, authorization, size-bound, and generic persistence integration coverage. |
| `backend/tests/test_freecad_plugin_e2e.py` | Package-install-to-analysis test using a stored FreeCAD fixture. |
| `plugins/freecad/tests/test_parser.py` | Parser-only fixture, malformed archive, and deterministic-output tests. |
| `frontend/src/App.test.tsx` and `frontend/e2e/usable-prototype.spec.ts` | Generic analysis interaction coverage and no-launch regression coverage. |
| `docs/PLUGIN_DEVELOPMENT.md`, `docs/API_REFERENCE.md`, `docs/PHASE_5_FREECAD_PLUGIN.md` | Public contract, workflow, limits, and fixture documentation. |
| `docs/adr/README.md`, `.github/automation/project/project.yaml` | ADR index and Phase 5 decision/work item tracking. |

---

### Task 1: Record the Generic Extension Decisions

**Files:**
- Create: `docs/adr/ADR-0047 - Authorize Bounded Representation Analysis Inputs.md`
- Create: `docs/adr/ADR-0048 - Accept Provider Analysis Contributions.md`
- Modify: `docs/adr/README.md`
- Modify: `.github/automation/project/project.yaml`
- Test: `scripts/validate_documentation.py`
- Test: `.github/automation/project/validate.py`

**Interfaces:**
- Consumes: ADR-0001, ADR-0002, ADR-0031, ADR-0034, ADR-0036, ADR-0039, and ADR-0040.
- Produces: approved architectural authority for `analysis_provider`, a 5 MiB bounded input, and generic Reference/Relationship contribution persistence.

- [ ] **Step 1: Write ADR-0047 as Proposed**

Define the decision as a generic representation-analysis input, not a FreeCAD contract:

```markdown
**Status:** Proposed

## Decision

Extension API v1 adds `analysis_provider`. A provider receives only one explicitly
requested Representation's generic identity, filename, media type, byte size,
SHA-256 digest and bounded base64 content after the Platform Core authorizes the
actor's read access. The default decoded-content limit is 5 MiB. The Platform
Core rejects oversized content before sandbox invocation and never exposes a
storage location or credential.
```

- [ ] **Step 2: Write ADR-0048 as Proposed**

Define the generic output contract and idempotency key:

```markdown
**Status:** Proposed

## Decision

An Analysis Provider may return Metadata Contributions, Reference Contributions,
and Relationship Contributions. Every contribution carries a provider-owned,
stable `contribution_key`. The owning Metadata and Relationships Platform
Modules authorize, validate and idempotently persist the contribution. A
Relationship Contribution is valid only when its source is the analyzed
Representation's owning Engineering Asset and its target is an existing
Engineering Asset the actor may access in the same Project.
```

- [ ] **Step 3: Add the decisions to project governance**

Add ADR-0047 and ADR-0048 to the ADR index. In the Mechanical Prototype Vertical
Slice epic, add a proposed-decision sub-issue or expand issue `#235` acceptance
criteria so implementation is explicitly blocked until both ADRs are Accepted.
Set the tracking fields to `Phase: Mechanical Engineering`, `Platform Area:
Extension API`, and `ADR: ADR-0047, ADR-0048`.

- [ ] **Step 4: Validate the proposed decisions**

Run: `uv run python scripts/validate_documentation.py`

Run: `uv run python .github/automation/project/validate.py .github/automation/project/project.yaml`

Expected: both commands exit `0`.

- [ ] **Step 5: Commit the decision proposal**

```bash
git add docs/adr/ADR-0047\ -\ Authorize\ Bounded\ Representation\ Analysis\ Inputs.md \
  docs/adr/ADR-0048\ -\ Accept\ Provider\ Analysis\ Contributions.md \
  docs/adr/README.md .github/automation/project/project.yaml
git commit -m "docs: propose analysis provider contracts"
```

- [ ] **Step 6: Stop for ADR acceptance**

Do not implement Tasks 2 through 9 until maintainers explicitly mark both ADRs
Accepted and the project configuration is reapplied. This is the architecture
approval gate required by `AGENTS.md`.

### Task 2: Define Analysis Provider Contracts and Contract Tests

**Files:**
- Modify: `backend/src/openpdm/extension_api/contracts.py`
- Modify: `backend/src/openpdm/extension_api/__init__.py`
- Modify: `backend/src/openpdm/extension_api/wit/openpdm-extension.wit`
- Modify: `backend/src/openpdm/extension_api/sdk.py`
- Modify: `backend/tests/test_extension_api_v1.py`

**Interfaces:**
- Consumes: accepted ADR-0047 and ADR-0048.
- Produces: `Capability.ANALYSIS_PROVIDER`, `RepresentationAnalysisInput`, `ReferenceContribution`, `RelationshipContribution`, and analysis fields on `InvocationResponse`.

- [ ] **Step 1: Write failing Extension API contract tests**

Add tests that validate the new capability, reject unknown fields, reject a
missing `contribution_key`, reject a cross-target relationship payload, and
preserve successful validation of the four existing capabilities:

```python
def test_analysis_contribution_requires_stable_key() -> None:
    with pytest.raises(ValidationError):
        ReferenceContribution(
            source_asset_id="asset-1", reference_type="plugin.ref",
            target_uri="plugin://ref/1", label="Reference", metadata={}
        )

def test_analysis_provider_is_additive_v1_capability() -> None:
    manifest = manifest(capabilities=[Capability.ANALYSIS_PROVIDER])
    assert manifest.capabilities == [Capability.ANALYSIS_PROVIDER]
```

- [ ] **Step 2: Run the focused contract test**

Run: `uv run pytest backend/tests/test_extension_api_v1.py -v`

Expected: FAIL because the analysis capability and contribution models do not exist.

- [ ] **Step 3: Add bounded, generic Pydantic models**

Use these exact public shapes in `contracts.py`:

```python
class RepresentationAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    representation_id: str = Field(min_length=1, max_length=36)
    asset_id: str = Field(min_length=1, max_length=36)
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0, le=5 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_base64: str = Field(min_length=1, max_length=7_000_000)

class ReferenceContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contribution_key: str = Field(min_length=1, max_length=255)
    source_asset_id: str = Field(min_length=1, max_length=36)
    reference_type: str = Field(min_length=1, max_length=255)
    target_uri: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)
```

Add the analogous `RelationshipContribution` with `target_asset_id`,
`relationship_type`, and `metadata`; add `analysis_input` to the invocation
payload and `references`/`relationships` lists to `InvocationResponse`. The WIT
world remains `invoke(request: string) -> string`; update generated SDK support
only for the JSON models, not with an additional host import.

- [ ] **Step 4: Run focused and package tests**

Run: `uv run pytest backend/tests/test_extension_api_v1.py -v`

Expected: PASS.

Run: `uv run ruff check backend/src/openpdm/extension_api backend/tests/test_extension_api_v1.py`

Expected: PASS.

- [ ] **Step 5: Commit the additive contract**

```bash
git add backend/src/openpdm/extension_api backend/tests/test_extension_api_v1.py
git commit -m "feat: add generic analysis provider contract"
```

### Task 3: Authorize and Invoke Bounded Representation Analysis

**Files:**
- Modify: `backend/src/openpdm/infrastructure/settings.py`
- Modify: `backend/src/openpdm/platform_core/modules/assets/contracts.py`
- Modify: `backend/src/openpdm/platform_core/modules/assets/service.py`
- Modify: `backend/src/openpdm/platform_core/modules/blobs/contracts.py`
- Modify: `backend/src/openpdm/platform_core/modules/blobs/service.py`
- Modify: `backend/src/openpdm/plugin_application.py`
- Create: `backend/tests/test_analysis_provider_api.py`

**Interfaces:**
- Consumes: `RepresentationAnalysisInput`, `PluginInvocationServices`, and the Assets/Blobs public interfaces.
- Produces: `invoke_analysis_provider(...)` returning validated but not yet persisted provider contributions.

- [ ] **Step 1: Write failing authorization and size-bound tests**

Create tests proving the orchestration layer:

```python
def test_analysis_input_requires_read_access_and_representation_blob(...) -> None:
    response = client.post(analysis_url, headers=other_user_headers, json=payload)
    assert response.status_code == 403

def test_analysis_input_rejects_content_above_configured_limit(...) -> None:
    response = client.post(analysis_url, headers=headers, json=payload)
    assert response.status_code == 413
    assert response.json()["detail"] == "Representation exceeds the analysis content limit."
```

Include a test for a Representation without a Blob (`409`) and one for an
inaccessible Blob (`403`).

- [ ] **Step 2: Run the focused API test**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py -v`

Expected: FAIL because no analysis operation or public input reader exists.

- [ ] **Step 3: Add public generic readers and the 5 MiB setting**

Add `plugin_analysis_max_content_bytes: int = 5 * 1024 * 1024` to `Settings`
with `Field(ge=1, le=5 * 1024 * 1024)`. Expose public methods that return an
authorized Representation and its Blob bytes only after checking the actor's
read access to the owning Engineering Asset. The application layer calls those
public methods through `MODULES.assets` and `MODULES.blobs`; it must not query
models or storage adapters itself.

Build the plugin request from server-owned values only:

```python
analysis_input = RepresentationAnalysisInput(
    representation_id=representation.id,
    asset_id=asset.id,
    filename=blob.filename,
    media_type=blob.media_type,
    size_bytes=blob.size_bytes,
    checksum_sha256=blob.checksum_sha256,
    content_base64=base64.b64encode(content).decode("ascii"),
)
```

Check `blob.size_bytes` before reading content. Pass `analysis_input` and the
caller-supplied mapping dictionary as plugin payload, then invoke only a plugin
that declares `analysis_provider` and is running.

- [ ] **Step 4: Run the authorization and lint checks**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py -v`

Expected: PASS.

Run: `uv run ruff check backend/src/openpdm backend/tests/test_analysis_provider_api.py`

Expected: PASS.

- [ ] **Step 5: Commit bounded input orchestration**

```bash
git add backend/src/openpdm/infrastructure/settings.py \
  backend/src/openpdm/platform_core/modules/assets \
  backend/src/openpdm/platform_core/modules/blobs \
  backend/src/openpdm/plugin_application.py backend/tests/test_analysis_provider_api.py
git commit -m "feat: authorize bounded representation analysis"
```

### Task 4: Persist Generic Analysis Contributions Through Owning Modules

**Files:**
- Modify: `backend/src/openpdm/platform_core/modules/relationships/contracts.py`
- Modify: `backend/src/openpdm/platform_core/modules/relationships/service.py`
- Modify: `backend/src/openpdm/plugin_application.py`
- Modify: `backend/tests/test_analysis_provider_api.py`

**Interfaces:**
- Consumes: validated `InvocationResponse.metadata`, `.references`, and `.relationships`.
- Produces: idempotent generic Metadata, Reference, and Relationship records plus existing audit/events.

- [ ] **Step 1: Extend failing tests for generic contribution rules**

Add cases that reject a provider result when:

```python
assert response.status_code == 400  # source Asset differs from analyzed Representation owner
assert response.status_code == 403  # mapped target Asset is unreadable or outside the Project
assert response.status_code == 400  # mapping key is not an extracted provider dependency
```

Add a success case invoking the same result twice. Assert exactly one metadata
entry, one Reference, and one Relationship exist for every stable
`contribution_key`, and that only the first invocation emits creation events.

- [ ] **Step 2: Run the focused persistence tests**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py -v`

Expected: FAIL because references and relationships are not accepted from a provider response.

- [ ] **Step 3: Add an idempotent public contribution method**

Add a public Relationships Platform Module method that receives generic
provider identity, `contribution_key`, source Asset, and a typed Reference or
Relationship contribution. Store the provider identity and contribution key in
the existing generic `metadata` JSON field, use them to find a matching prior
record, and return it without a duplicate audit/event when it already exists.

`plugin_application.invoke_analysis_provider` must perform these checks before
persistence:

```python
if contribution.source_asset_id != analyzed_asset.id:
    raise HTTPException(400, "Analysis Provider may only contribute from the analyzed Asset.")
if target_asset.project_id != analyzed_asset.project_id:
    raise HTTPException(400, "Analysis Provider target must belong to the analyzed Project.")
```

Persist metadata through `MetadataModule.put_entry`, then references and
relationships through the Relationships Platform Module public method. Do not
add a FreeCAD table, column, route, event, or relationship rule.

- [ ] **Step 4: Run contribution, existing graph, and database checks**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py backend/tests/test_core_platform_api.py -v`

Expected: PASS.

Run: `uv run ruff format --check backend/src/openpdm backend/tests/test_analysis_provider_api.py`

Expected: PASS.

- [ ] **Step 5: Commit generic contribution persistence**

```bash
git add backend/src/openpdm/platform_core/modules/relationships \
  backend/src/openpdm/plugin_application.py backend/tests/test_analysis_provider_api.py
git commit -m "feat: persist generic analysis contributions"
```

### Task 5: Publish the Analysis Route and Generic Web UI Workflow

**Files:**
- Modify: `backend/src/openpdm/api/core.py`
- Modify: `backend/tests/test_analysis_provider_api.py`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/e2e/prototype-fixtures.ts`
- Modify: `frontend/e2e/usable-prototype.spec.ts`

**Interfaces:**
- Consumes: `POST /plugins/{plugin_id}/providers/analysis` request fields `representation_id`, `project_id`, `organization_id`, and optional `relationship_mappings`.
- Produces: generic `AnalysisResult` containing persisted metadata, references, and relationships.

- [ ] **Step 1: Write failing route and client tests**

Add API tests for the exact route contract:

```python
response = client.post(
    f"/plugins/{plugin_id}/providers/analysis",
    headers=headers,
    json={
        "representation_id": representation_id,
        "project_id": project_id,
        "organization_id": organization_id,
        "relationship_mappings": {"dependency-key": target_asset_id},
    },
)
assert response.status_code == 200
assert set(response.json()) == {"metadata", "references", "relationships"}
```

In `App.test.tsx`, mock a discovered provider with `analysis_provider`, select a
Representation, click `Analyze representation`, and assert the generic result
count and refreshed metadata/reference/relationship panels. Assert that the
rendered DOM contains no command, executable, or launch button.

- [ ] **Step 2: Run route and frontend tests**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py -v`

Run: `pnpm --dir frontend test -- --run App.test.tsx`

Expected: FAIL because the route and client action do not exist.

- [ ] **Step 3: Implement the public route and typed client**

Add these models to `api/core.py`:

```python
class InvokeAnalysisProviderRequest(BaseModel):
    representation_id: str
    project_id: str
    organization_id: str | None = None
    relationship_mappings: dict[str, str] = Field(default_factory=dict, max_length=100)

class AnalysisResultResponse(BaseModel):
    metadata: list[MetadataResponse]
    references: list[ReferenceResponse]
    relationships: list[RelationshipResponse]
```

The route uses `invoke_analysis_provider`, commits only after all generic
contributions are validated, and serializes the existing record views. Include
`analysis_provider` in `GET /providers` capability filtering.

In `frontend/src/api.ts`, add `AnalysisResult` and `invokeAnalysisProvider()`.
In `App.tsx`, derive Representation choices from the selected Engineering
Asset's existing revisions, render only discovered `analysis_provider` actions,
and call the typed client. The label is exactly `Analyze representation`; it
does not mention FreeCAD or any executable. Disable while busy, show a normal
failure banner, and refresh the generic record panels after success.

- [ ] **Step 4: Run browser, component, and API verification**

Run: `uv run pytest backend/tests/test_analysis_provider_api.py -v`

Run: `pnpm --dir frontend test -- --run App.test.tsx`

Run: `pnpm --dir frontend exec playwright test e2e/usable-prototype.spec.ts --project=chromium`

Expected: PASS, with no external-program launch behavior.

- [ ] **Step 5: Commit the generic application surfaces**

```bash
git add backend/src/openpdm/api/core.py backend/tests/test_analysis_provider_api.py \
  frontend/src/api.ts frontend/src/App.tsx frontend/src/App.test.tsx \
  frontend/e2e/prototype-fixtures.ts frontend/e2e/usable-prototype.spec.ts
git commit -m "feat: invoke representation analysis providers"
```

### Task 6: Build the FreeCAD Official Plugin and Fixture Manifest

**Files:**
- Create: `plugins/freecad/openpdm-plugin.json`
- Create: `plugins/freecad/freecad_plugin.py`
- Create: `plugins/freecad/fixtures.json`
- Create: `plugins/freecad/README.md`
- Create: `plugins/freecad/tests/test_parser.py`
- Create: `scripts/build_freecad_plugin.py`
- Modify: `sample/freecad/README.md`

**Interfaces:**
- Consumes: `analysis_provider` JSON request with `analysis_input` and `relationship_mappings`.
- Produces: plugin-owned `freecad.*` metadata, `freecad://` References for unmapped document links, and mapped generic `depends_on` Relationships.

- [ ] **Step 1: Write failing parser tests from immutable fixtures**

Create `fixtures.json` with each file's SHA-256. Include this minimum expected
record for the assembly fixture:

```json
{
  "filename": "AssemblyExample.FCStd",
  "label": "AssemblyExample",
  "object_count": 53,
  "document_link_count": 13
}
```

Add tests that read the fixture bytes directly and verify label/object/link
counts, sorted output, rejection of a non-ZIP payload, rejection of a ZIP
without `Document.xml`, and rejection when decoded bytes exceed the plugin's
declared 5 MiB input limit.

- [ ] **Step 2: Run parser tests to confirm the missing implementation**

Run: `uv run pytest plugins/freecad/tests/test_parser.py -v`

Expected: FAIL because the plugin parser does not exist.

- [ ] **Step 3: Implement a sandbox-only `.FCStd` parser**

Use `base64`, `io.BytesIO`, `zipfile.ZipFile`, and `xml.etree.ElementTree`; do
not import `FreeCAD`, call `subprocess`, or inspect the local filesystem.

```python
def parse_fcstd(content: bytes) -> FreecadDocument:
    with ZipFile(BytesIO(content)) as archive:
        if "Document.xml" not in archive.namelist():
            raise PluginFailure("freecad.invalid_archive", "Document.xml is required.")
        root = ElementTree.fromstring(archive.read("Document.xml"))
    return FreecadDocument(
        label=read_document_label(root),
        object_count=read_object_count(root),
        links=sorted(read_document_links(root)),
    )
```

For `operation == "analysis"`, return deterministic entries such as
`freecad.document.label`, `freecad.document.object_count`, and
`freecad.document.link_count`. Create an unmapped Reference with an opaque,
plugin-owned `freecad://document/<checksum>/object/<name>` URI for each
extracted link. Use `relationship_mappings[link_key]` only when supplied; then
return a generic relationship whose source is the provided `asset_id` and whose
target is the mapped Asset. The plugin chooses `depends_on`; the Platform Core
does not.

- [ ] **Step 4: Build and package the Official Plugin**

Mirror `scripts/build_reference_plugin.py`. The manifest uses:

```json
{
  "id": "org.openpdm.freecad",
  "name": "FreeCAD Analysis",
  "version": "0.1.0",
  "extension_api_versions": [1],
  "capabilities": ["analysis_provider"],
  "component": "freecad_plugin.wasm"
}
```

Run: `uv run python scripts/build_freecad_plugin.py --output plugins/freecad/dist/freecad.openpdm-plugin`

Expected: a validated package is produced without starting FreeCAD or any
other executable.

- [ ] **Step 5: Run parser, package, and sandbox checks**

Run: `uv run pytest plugins/freecad/tests/test_parser.py backend/tests/test_extension_api_v1.py -v`

Run: `uv run ruff check plugins/freecad scripts/build_freecad_plugin.py`

Expected: PASS.

- [ ] **Step 6: Commit the Official Plugin**

```bash
git add plugins/freecad scripts/build_freecad_plugin.py sample/freecad/README.md
git commit -m "feat: add FreeCAD analysis official plugin"
```

### Task 7: Prove the End-to-End Mechanical Vertical Slice

**Files:**
- Create: `backend/tests/test_freecad_plugin_e2e.py`
- Modify: `backend/tests/test_analysis_provider_api.py`
- Modify: `docs/PHASE_5_FREECAD_PLUGIN.md`

**Interfaces:**
- Consumes: built `org.openpdm.freecad` package and public plugin lifecycle/analysis routes.
- Produces: a reproducible proof that a stored `.FCStd` produces generic records under normal authorization.

- [ ] **Step 1: Write the failing full-journey test**

Follow `test_reference_plugin_e2e.py`: build the package, register the Platform
Administrator, create an Organization, Project, source Engineering Asset, and
target Engineering Asset, upload `AssemblyExample.FCStd`, attach it as a
Representation, install it as `official`, enable it, discover the provider, and
invoke analysis twice.

Assert:

```python
assert metadata["freecad.document.label"]["value"] == "AssemblyExample"
assert metadata["freecad.document.object_count"]["value"] == 53
assert len(references) == 13
assert len(relationships) == 1
assert relationship["source_asset_id"] == source_asset_id
assert relationship["target_asset_id"] == target_asset_id
```

Use a mapping for exactly one named dependency. Re-run with the same mapping
and assert the record counts do not increase. Add a separate call without a
mapping and assert it produces References but no Relationships.

- [ ] **Step 2: Run the E2E test before adding any test-specific shortcut**

Run: `uv run pytest backend/tests/test_freecad_plugin_e2e.py -v`

Expected: FAIL until Tasks 2 through 6 are complete.

- [ ] **Step 3: Make the journey pass through public paths only**

Do not access plugin modules, repositories, object storage, or database rows
from the test to create the result. The test may use the local fixture only to
upload bytes and to assert documented values. Keep package installation,
lifecycle activation, discovery, and analysis invocation on public HTTP routes.

- [ ] **Step 4: Run focused regression coverage**

Run: `uv run pytest backend/tests/test_freecad_plugin_e2e.py backend/tests/test_reference_plugin_e2e.py backend/tests/test_dummy_categories_plugin_e2e.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the proof**

```bash
git add backend/tests/test_freecad_plugin_e2e.py backend/tests/test_analysis_provider_api.py \
  docs/PHASE_5_FREECAD_PLUGIN.md
git commit -m "test: prove FreeCAD plugin vertical slice"
```

### Task 8: Reconcile Documentation and Project Tracking

**Files:**
- Modify: `docs/PLUGIN_DEVELOPMENT.md`
- Modify: `docs/API_REFERENCE.md`
- Create: `docs/PHASE_5_FREECAD_PLUGIN.md`
- Modify: `docs/adr/README.md`
- Modify: `.github/automation/project/project.yaml`

**Interfaces:**
- Consumes: accepted ADR-0047/0048, the public route, and the released plugin package.
- Produces: accurate user and contributor guidance with no implied FreeCAD executable launch.

- [ ] **Step 1: Add public analysis-provider documentation**

In `PLUGIN_DEVELOPMENT.md`, document `analysis_provider` as a generic provider
with bounded content and generic contributions. In `API_REFERENCE.md`, add:

```text
POST /plugins/{plugin_id}/providers/analysis
```

Document the request fields, 413 content-limit response, authorization rules,
and generic response arrays. Do not name FreeCAD in either generic contract
section.

- [ ] **Step 2: Write the FreeCAD workflow guide**

`docs/PHASE_5_FREECAD_PLUGIN.md` must state: supported `.FCStd` analysis;
fixture origin; plugin metadata keys; unmapped links as References; explicit
mapping requirement for Relationships; 5 MiB limit; unsupported STEP parsing,
BOMs, previews, conversion, file mutation, desktop sync, and all executable
launch behavior. Include the public administrator and user workflow with API
and generic Web UI paths.

- [ ] **Step 3: Update Phase 5 issue acceptance criteria**

In `project.yaml`, link implementation work to ADR-0047 and ADR-0048, the
FreeCAD fixture corpus, the no-executable-launch constraint, public API
coverage, and the installation-to-analysis E2E test. Keep SOLIDWORKS out of
the Phase 5 scope.

- [ ] **Step 4: Run documentation and project validation**

Run: `uv run python scripts/validate_documentation.py`

Run: `uv run python .github/automation/project/validate.py .github/automation/project/project.yaml`

Expected: PASS.

- [ ] **Step 5: Commit documentation and tracking updates**

```bash
git add docs/PLUGIN_DEVELOPMENT.md docs/API_REFERENCE.md docs/PHASE_5_FREECAD_PLUGIN.md \
  docs/adr/README.md .github/automation/project/project.yaml
git commit -m "docs: document FreeCAD analysis workflow"
```

### Task 9: Run the Phase 5 Acceptance Gate

**Files:**
- Modify: `docs/PROTOTYPE_ACCEPTANCE.md`
- Modify: `docs/PHASE_5_FREECAD_PLUGIN.md`

**Interfaces:**
- Consumes: complete behavior from Tasks 2 through 8.
- Produces: recorded automated and manual evidence for the mechanical vertical slice.

- [ ] **Step 1: Record a test matrix before executing it**

Add a table to `docs/PHASE_5_FREECAD_PLUGIN.md` with these rows: valid
`.FCStd`, malformed archive, unsupported STEP, oversized content, no Blob,
unauthorized actor, unmapped link, mapped link, repeated analysis, disabled
plugin, and existing-provider regression. Mark each row with its exact test or
manual evidence location.

- [ ] **Step 2: Run the full quality suite**

Run: `uv run pytest backend/tests -v`

Run: `uv run ruff format --check backend tests plugins scripts`

Run: `uv run ruff check backend tests plugins scripts`

Run: `pnpm --dir frontend lint`

Run: `pnpm --dir frontend test -- --run`

Run: `pnpm --dir frontend build`

Run: `pnpm --dir frontend exec playwright test --project=chromium`

Expected: every command exits `0`.

- [ ] **Step 3: Perform and record the manual local-service smoke check**

Using the documented local startup path, install and enable the built Official
Plugin, upload `AssemblyExample.FCStd`, select its Representation through the
generic analysis action, analyze once unmapped and once with an explicit Asset
mapping, then verify the resulting metadata, Reference, Relationship, timeline,
and audit evidence. Confirm no executable or external process starts.

- [ ] **Step 4: Commit the acceptance evidence**

```bash
git add docs/PROTOTYPE_ACCEPTANCE.md docs/PHASE_5_FREECAD_PLUGIN.md
git commit -m "docs: record FreeCAD plugin acceptance evidence"
```

## Plan Self-Review

* **Spec coverage:** Tasks 1-4 protect the generic architectural boundary; Tasks 5-7 deliver and prove the first usable slice; Tasks 8-9 document, track, and accept it. The FreeCAD fixture corpus, deterministic parser, bounded input, explicit mapping, no-process constraint, and desktop deferral are all covered.
* **Placeholder scan:** No task depends on unspecified behavior. The two unresolved architecture decisions are explicitly represented by ADR-0047 and ADR-0048 and block implementation until acceptance.
* **Type consistency:** `analysis_provider`, `RepresentationAnalysisInput`, `ReferenceContribution`, `RelationshipContribution`, `InvokeAnalysisProviderRequest`, and `AnalysisResultResponse` use the same names from contract through UI and tests.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-freecad-mechanical-plugin.md`.

1. **Subagent-Driven (recommended):** dispatch a fresh subagent per task and review each task before proceeding.
2. **Inline Execution:** execute tasks in this session using the plan checkpoints.
