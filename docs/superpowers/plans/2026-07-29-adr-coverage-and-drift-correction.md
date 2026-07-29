# ADR Coverage And Drift Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add missing ADR and documentation coverage for implemented OpenPDM decisions, then correct the implementation drift found during the ADR audit.

**Architecture:** First document decisions that already exist in the repository as proposed ADRs, then align public documentation with those decisions, then correct code drift without introducing new architecture. The implementation fixes preserve Platform Core boundaries by routing plugin orchestration through the composition root or explicit public contracts, and preserve database migration discipline by separating development/test schema creation from production startup.

**Tech Stack:** Markdown ADRs and docs, Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, pytest, Ruff, React, TypeScript, Vite, Tauri, Wasmtime.

## Global Constraints

- Read `AGENTS.md`, `docs/PROJECT_CHARTER.md`, `docs/ARCHITECTURE.md`, `docs/VISION.md`, `ROADMAP.md`, and accepted ADRs before implementation.
- Use official terminology: Platform Core, Platform Modules, Extension API, Official Plugins, Community Plugins, Engineering Asset.
- Do not add engineering-domain semantics to the Platform Core.
- Do not introduce privileged APIs for Official Plugins.
- Do not bypass the Extension API.
- Keep changes focused: ADR/documentation changes first, drift correction second.
- Draft new ADRs as `Proposed` unless the maintainer explicitly asks to mark them `Accepted`.
- Use `apply_patch` for manual file edits.
- Run targeted tests after every task.

---

## File Structure

- Create `docs/adr/ADR-0044 - Adopt The Web UI Operational Interaction Stack.md`: documents the existing Web UI choices not covered by ADR-0007.
- Create `docs/adr/ADR-0045 - Persist Client-Side Resumable Transfer Recovery.md`: documents browser-side recovery state that complements ADR-0042.
- Create `docs/adr/ADR-0046 - Define Schema Initialization And Migration Discipline.md`: documents how Alembic and development/test schema creation should coexist.
- Modify `docs/adr/README.md`: add a compact ADR index entry for ADR-0044 through ADR-0046 if this README already functions as the ADR guide.
- Modify `docs/DEVELOPMENT.md`: document the frontend interaction stack, transfer recovery behavior, and direct-backend database setup expectations.
- Modify `docs/DEPLOYMENT.md`: clarify that Compose uses Alembic and that application startup should not be the production migration mechanism.
- Modify `docs/API_REFERENCE.md`: add or verify concise documentation for upload-session recovery-facing fields and private Project Asset views.
- Modify `backend/src/openpdm/plugin_application.py`: replace direct imports from `openpdm.platform_core.modules.services` with composition-root or public-contract dependencies.
- Modify `backend/src/openpdm/plugin_runtime/dispatcher.py`: replace direct `PluginsModule` import with composition-root or public-contract dependency.
- Modify `tests/test_architecture_boundaries.py`: extend boundary tests to cover plugin orchestration and runtime dispatcher modules.
- Modify `backend/src/openpdm/main.py`: remove duplicate schema initialization from application creation once lifespan owns startup initialization.
- Modify `backend/src/openpdm/api/core.py`: make lifespan schema initialization explicit for local/test/dev only, or call a renamed helper that states its scope.
- Modify `backend/src/openpdm/infrastructure/database.py`: rename or split `initialize_database()` if needed so direct `create_all` cannot be mistaken for production migration.
- Add or modify backend tests under `backend/tests/` or repository tests under `tests/` to lock the migration/startup boundary.

---

### Task 1: Create Missing ADRs

**Files:**
- Create: `docs/adr/ADR-0044 - Adopt The Web UI Operational Interaction Stack.md`
- Create: `docs/adr/ADR-0045 - Persist Client-Side Resumable Transfer Recovery.md`
- Create: `docs/adr/ADR-0046 - Define Schema Initialization And Migration Discipline.md`
- Modify: `docs/adr/README.md`

**Interfaces:**
- Consumes: existing ADR numbering and ADR tone from `docs/adr/ADR-0043 - Persist Private Per-User Project Views.md`.
- Produces: three proposed ADRs that later documentation and implementation drift fixes can cite.

- [ ] **Step 1: Confirm next ADR number**

Run:

```powershell
Get-ChildItem docs/adr -File | Sort-Object Name | Select-Object Name
```

Expected: highest numbered ADR is `ADR-0043`.

- [ ] **Step 2: Create ADR-0044 for the Web UI operational interaction stack**

Write `docs/adr/ADR-0044 - Adopt The Web UI Operational Interaction Stack.md` with this decision:

```markdown
# ADR-0044 - Adopt The Web UI Operational Interaction Stack

**Status:** Proposed

---

# Context

ADR-0007 selects React, TypeScript and Vite for the Web UI. The current Web UI has also standardized on React Router for durable application routes, Radix primitives for dialogs, menus, tabs, tooltips and toasts, Lucide for interface icons, Vitest for component and API-client tests, Playwright for browser acceptance checks, and repository-owned CSS tokens for the operational workspace shell.

These choices now affect application structure, testing, accessibility, and contributor workflow. Leaving them undocumented makes future Web UI work more likely to introduce inconsistent interaction primitives, duplicated routing patterns or ungoverned design-system drift.

---

# Decision

OpenPDM will treat the current Web UI operational interaction stack as the default implementation stack for the browser-based application:

* React Router owns durable client routes.
* Radix primitives provide accessible interaction foundations for dialogs, menus, tabs, toasts and tooltips.
* Lucide provides interface icons.
* Repository-owned CSS tokens and styles provide the visual system.
* Vitest covers unit and component behavior.
* Playwright covers browser acceptance and prototype workflow checks.

The Web UI remains an application client. It consumes only the public application API and must not depend on Platform Module internals or plugin implementation details.

This decision does not introduce a general design system package, plugin-defined frontend components or executable UI injection.

---

# Consequences

## Positive

* Web UI contributors have one documented interaction stack.
* Accessibility-oriented primitives remain consistent across the application.
* Browser acceptance checks become part of the expected frontend quality gate.
* The application-client boundary remains aligned with the API-first principle.

## Trade-offs

* Replacing the interaction stack later requires a deliberate compatibility decision.
* Contributors should prefer existing primitives over ad hoc components.
* The current CSS token system must be maintained as shared UI surface.

---

# Review

Reconsider this decision if OpenPDM adopts a packaged design system, a different routing model, or a separately sandboxed application-extension model.
```

- [ ] **Step 3: Create ADR-0045 for client-side transfer recovery**

Write `docs/adr/ADR-0045 - Persist Client-Side Resumable Transfer Recovery.md` with this decision:

```markdown
# ADR-0045 - Persist Client-Side Resumable Transfer Recovery

**Status:** Proposed

---

# Context

ADR-0042 defines storage-independent resumable Blob upload sessions owned by the Blobs Platform Module. The Web UI currently complements that server contract by storing minimal per-user, per-Asset transfer recovery state in browser `sessionStorage`.

The stored client state contains session identity and file identity so an interrupted check-in can resume against the public upload-session API. It does not contain file bytes, object-storage keys, credentials or authority.

This behavior affects user recovery, security expectations and future desktop/browser alignment, but it is not currently captured by an ADR.

---

# Decision

OpenPDM application clients may persist bounded, local transfer recovery state for resumable Blob uploads.

For the Web UI, recovery state is scoped by authenticated user and Engineering Asset, stored in browser `sessionStorage`, and limited to:

* user identifier;
* Asset identifier;
* upload session identifier;
* selected file name, size, media type and last-modified timestamp;
* completed Blob identifier only after server completion succeeds.

Clients must revalidate recovery state with the public application API before reuse. The server remains the authority for upload-session status, ownership, Project authorization, accepted chunks and completed Blob records.

Client recovery state must never include Blob bytes, provider object keys, storage credentials, plugin data, authorization tokens beyond the normal application session mechanism, or engineering-domain semantics.

---

# Consequences

## Positive

* Users can recover interrupted transfers without restarting successful chunks.
* Server-side upload-session ownership and authorization remain authoritative.
* Browser-local recovery stays bounded and avoids storing file contents.
* The Web UI behavior is now documented for future desktop and browser work.

## Trade-offs

* Recovery is limited to the current browser session storage lifetime.
* Clients must handle stale, mismatched or revoked sessions cleanly.
* Broader offline sync or durable desktop transfer queues require a future ADR.

---

# Review

Reconsider this decision when OpenPDM introduces desktop synchronization, offline transfer queues or cross-device transfer recovery.
```

- [ ] **Step 4: Create ADR-0046 for schema initialization and migrations**

Write `docs/adr/ADR-0046 - Define Schema Initialization And Migration Discipline.md` with this decision:

```markdown
# ADR-0046 - Define Schema Initialization And Migration Discipline

**Status:** Proposed

---

# Context

ADR-0005 selects PostgreSQL as the primary database and Alembic for schema migrations. The current deployment backend runs `alembic upgrade head` before starting the API, while local and test code can create the current SQLAlchemy schema directly.

Direct metadata creation is useful for isolated tests and fast local prototypes, but it can blur production expectations if application startup is treated as a migration mechanism. OpenPDM needs a clear rule that preserves Alembic discipline without making tests unnecessarily slow.

---

# Decision

OpenPDM uses Alembic as the authoritative schema migration mechanism for persistent deployments.

Direct SQLAlchemy metadata creation is allowed only for development and automated test contexts that create disposable databases. The helper name and documentation must make that limited scope explicit.

The backend application must not rely on direct metadata creation as the production schema upgrade path. Deployment entrypoints must run Alembic migrations before serving traffic. Tests may continue to exercise direct disposable schema creation when the test's purpose is not migration behavior.

When a new persistent table, column, constraint or index is introduced, the change must include an Alembic migration and a focused upgrade test when practical.

---

# Consequences

## Positive

* Persistent deployments have one authoritative migration path.
* Fast disposable test setup remains available.
* Future schema changes are less likely to exist only in SQLAlchemy models.
* The implementation aligns more clearly with ADR-0005.

## Trade-offs

* Startup code must distinguish deployment readiness from disposable test initialization.
* Contributors must maintain migrations even when model changes appear simple.
* Existing local databases may require explicit migration commands.

---

# Review

Reconsider this decision if OpenPDM replaces Alembic, introduces a separate migration service, or adopts a different persistence model.
```

- [ ] **Step 5: Update ADR README index**

Append the three ADRs to the README's lifecycle or index area if an index exists. If no index exists, add this compact section near the end:

```markdown
## Current ADRs

Recent ADRs:

* ADR-0044 - Adopt The Web UI Operational Interaction Stack
* ADR-0045 - Persist Client-Side Resumable Transfer Recovery
* ADR-0046 - Define Schema Initialization And Migration Discipline
```

- [ ] **Step 6: Validate Markdown links and ADR filenames**

Run:

```powershell
uv run python scripts/validate_documentation.py
```

Expected: documentation validation passes.

- [ ] **Step 7: Commit ADR drafts**

Run:

```powershell
git add docs/adr
git commit -m "docs: propose ADRs for implementation coverage gaps"
```

Expected: one focused documentation commit.

---

### Task 2: Update Documentation For ADR Coverage

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/ARCHITECTURE.md` only if it already mentions the affected behavior and needs a small pointer.

**Interfaces:**
- Consumes: ADR-0044, ADR-0045 and ADR-0046 from Task 1.
- Produces: user and contributor documentation that matches implemented behavior.

- [ ] **Step 1: Document frontend stack in DEVELOPMENT**

In `docs/DEVELOPMENT.md`, update the Web UI section to mention:

```markdown
The Web UI operational stack is documented by ADR-0044. New Web UI work should prefer the existing React Router route model, Radix interaction primitives, Lucide icons, Vitest unit/component tests, Playwright browser checks, and repository-owned CSS tokens before introducing another UI dependency or pattern.
```

- [ ] **Step 2: Document transfer recovery in DEVELOPMENT**

Add a short subsection under Web UI development:

```markdown
### Resumable Transfer Recovery

The Web UI stores minimal resumable upload recovery state in browser `sessionStorage`, scoped by user and Engineering Asset. The stored state contains upload-session identity and selected-file identity, not file bytes, storage keys or credentials. On reuse, the Web UI revalidates the session through the public upload-session API before sending more chunks.
```

- [ ] **Step 3: Clarify migration discipline in DEPLOYMENT**

In `docs/DEPLOYMENT.md`, update the migration note to state:

```markdown
Alembic is the authoritative schema migration path for persistent deployments. The Compose backend runs `alembic upgrade head` before serving the API. Direct SQLAlchemy schema creation is reserved for disposable development and automated test databases, as described by ADR-0046.
```

- [ ] **Step 4: Update API reference for upload-session recovery fields**

In `docs/API_REFERENCE.md`, ensure `/blobs/upload-sessions` documents:

```markdown
Upload-session responses include `id`, `asset_id`, file identity fields, `chunk_size_bytes`, `received_bytes`, `received_chunk_numbers`, `status`, `expires_at`, and `blob`. Clients may use these fields to resume a transfer, but must treat the server response as authoritative.
```

- [ ] **Step 5: Update API reference for private Project Asset views**

In `docs/API_REFERENCE.md`, ensure `/users/me/project-views` documents:

```markdown
Project Asset views are private to the authenticated user and scoped to one Project. Stored filters, sort, density and selected columns are revalidated when applied to Engineering Asset queries and never grant access by themselves.
```

- [ ] **Step 6: Validate docs**

Run:

```powershell
uv run python scripts/validate_documentation.py
```

Expected: documentation validation passes.

- [ ] **Step 7: Commit documentation updates**

Run:

```powershell
git add docs/DEVELOPMENT.md docs/DEPLOYMENT.md docs/API_REFERENCE.md docs/ARCHITECTURE.md
git commit -m "docs: align guides with ADR coverage"
```

Expected: one focused documentation commit.

---

### Task 3: Correct Plugin Boundary Drift

**Files:**
- Modify: `backend/src/openpdm/plugin_application.py`
- Modify: `backend/src/openpdm/plugin_runtime/dispatcher.py`
- Modify: `tests/test_architecture_boundaries.py`

**Interfaces:**
- Consumes: `MODULES` from `backend/src/openpdm/platform_core/composition.py`.
- Produces: plugin orchestration that no longer imports `openpdm.platform_core.modules.services` directly.

- [ ] **Step 1: Write failing boundary test**

Add this test to `tests/test_architecture_boundaries.py`:

```python
def test_plugin_orchestration_uses_composition_root_not_module_implementations() -> None:
    checked = [
        BACKEND_SRC / "plugin_application.py",
        BACKEND_SRC / "plugin_runtime" / "dispatcher.py",
    ]
    violations: list[str] = []
    for source_file in checked:
        imports = imported_modules(source_file)
        if any(name.startswith("openpdm.platform_core.modules.services") for name in imports):
            violations.append(str(source_file.relative_to(ROOT)))
    assert violations == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_architecture_boundaries.py::test_plugin_orchestration_uses_composition_root_not_module_implementations -q
```

Expected: FAIL listing `backend/src/openpdm/plugin_application.py` and `backend/src/openpdm/plugin_runtime/dispatcher.py`.

- [ ] **Step 3: Update plugin_application imports**

Replace:

```python
from openpdm.platform_core.modules.services import AssetsModule, MetadataModule, PluginsModule
```

with:

```python
from openpdm.platform_core.composition import MODULES

AssetsModule = MODULES.assets
MetadataModule = MODULES.metadata
PluginsModule = MODULES.plugins
```

- [ ] **Step 4: Update dispatcher imports**

Replace:

```python
from openpdm.platform_core.modules.services import PluginsModule
```

with:

```python
from openpdm.platform_core.composition import MODULES

PluginsModule = MODULES.plugins
```

- [ ] **Step 5: Run focused plugin tests**

Run:

```powershell
uv run pytest tests/test_architecture_boundaries.py backend/tests/test_plugin_configuration_events.py backend/tests/test_reference_plugin_e2e.py backend/tests/test_dummy_categories_plugin_e2e.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit plugin boundary fix**

Run:

```powershell
git add backend/src/openpdm/plugin_application.py backend/src/openpdm/plugin_runtime/dispatcher.py tests/test_architecture_boundaries.py
git commit -m "fix: route plugin orchestration through composition root"
```

Expected: one focused drift-correction commit.

---

### Task 4: Correct Schema Initialization Drift

**Files:**
- Modify: `backend/src/openpdm/infrastructure/database.py`
- Modify: `backend/src/openpdm/main.py`
- Modify: `backend/src/openpdm/api/core.py`
- Add or modify: `tests/test_database_initialization.py`
- Verify: `backend/Dockerfile`

**Interfaces:**
- Consumes: ADR-0046 from Task 1.
- Produces: clear separation between Alembic deployment migrations and disposable schema initialization.

- [ ] **Step 1: Write test for app factory not directly initializing schema**

Create `tests/test_database_initialization.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_factory_does_not_directly_initialize_schema() -> None:
    main_source = (ROOT / "backend" / "src" / "openpdm" / "main.py").read_text(encoding="utf-8")

    assert "initialize_database()" not in main_source
    assert "initialize_disposable_database()" not in main_source
```

- [ ] **Step 2: Write test for disposable helper naming**

Add to `tests/test_database_initialization.py`:

```python
def test_direct_schema_creation_is_named_as_disposable() -> None:
    database_source = (
        ROOT / "backend" / "src" / "openpdm" / "infrastructure" / "database.py"
    ).read_text(encoding="utf-8")

    assert "def initialize_disposable_database(" in database_source
    assert "metadata.create_all" in database_source
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_database_initialization.py -q
```

Expected: FAIL because the helper is still named `initialize_database` and `main.py` calls it.

- [ ] **Step 4: Rename disposable schema helper**

In `backend/src/openpdm/infrastructure/database.py`, replace:

```python
def initialize_database(settings: Settings | None = None) -> None:
    """Create the current schema for local development and tests."""
    from openpdm.platform_core.modules.models import Base as PlatformBase

    PlatformBase.metadata.create_all(get_engine(settings))
```

with:

```python
def initialize_disposable_database(settings: Settings | None = None) -> None:
    """Create the current schema only for disposable development and test databases."""
    from openpdm.platform_core.modules.models import Base as PlatformBase

    PlatformBase.metadata.create_all(get_engine(settings))
```

- [ ] **Step 5: Add compatibility alias only if needed**

If too many tests still import `initialize_database`, add this temporary compatibility wrapper and document it for later removal:

```python
def initialize_database(settings: Settings | None = None) -> None:
    """Compatibility wrapper for tests; prefer initialize_disposable_database."""
    initialize_disposable_database(settings)
```

If tests can be updated in this task without excessive churn, update imports instead and do not add the wrapper.

- [ ] **Step 6: Remove app factory schema creation**

In `backend/src/openpdm/main.py`, remove:

```python
from openpdm.infrastructure.database import initialize_database
```

and remove this call from `create_app()`:

```python
initialize_database()
```

- [ ] **Step 7: Update lifespan initialization naming**

In `backend/src/openpdm/api/core.py`, replace imports and calls so lifespan uses the disposable helper name only for local/test startup:

```python
from openpdm.infrastructure.database import (
    get_db_session,
    initialize_disposable_database,
    session_scope,
)
```

and:

```python
initialize_disposable_database()
```

If ADR-0046 is accepted with a stricter production rule before implementation, gate this call behind a setting such as `OPENPDM_AUTO_CREATE_DISPOSABLE_SCHEMA=false` and keep Compose dependent on Alembic.

- [ ] **Step 8: Update tests importing initialize_database**

Replace test imports:

```python
from openpdm.infrastructure.database import initialize_database
```

with:

```python
from openpdm.infrastructure.database import initialize_disposable_database
```

Replace calls accordingly in backend tests that create SQLite or disposable databases.

- [ ] **Step 9: Run focused tests**

Run:

```powershell
uv run pytest tests/test_database_initialization.py tests/test_architecture_boundaries.py backend/tests/test_foundation_api.py backend/tests/test_operational_collections.py backend/tests/test_blob_upload_sessions.py -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit schema drift fix**

Run:

```powershell
git add backend/src/openpdm/infrastructure/database.py backend/src/openpdm/main.py backend/src/openpdm/api/core.py backend/tests tests/test_database_initialization.py
git commit -m "fix: clarify disposable schema initialization"
```

Expected: one focused drift-correction commit.

---

### Task 5: Final Verification And Review Notes

**Files:**
- No planned source edits.
- Read: `git diff --stat`
- Read: `git log --oneline -5`

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: validated branch ready for maintainer review.

- [ ] **Step 1: Run full backend and architecture tests**

Run:

```powershell
uv run pytest -q
```

Expected: all non-environment-skipped tests pass.

- [ ] **Step 2: Run documentation validation**

Run:

```powershell
uv run python scripts/validate_documentation.py
```

Expected: documentation validation passes.

- [ ] **Step 3: Run frontend checks if dependencies are available**

Run:

```powershell
cd frontend
pnpm run lint
pnpm run test
```

Expected: TypeScript and Vitest pass. If `pnpm` is unavailable, record that frontend checks were not run.

- [ ] **Step 4: Review git diff**

Run:

```powershell
git diff --stat
git diff -- docs/adr docs/DEVELOPMENT.md docs/DEPLOYMENT.md docs/API_REFERENCE.md
git diff -- backend/src/openpdm/plugin_application.py backend/src/openpdm/plugin_runtime/dispatcher.py backend/src/openpdm/infrastructure/database.py backend/src/openpdm/main.py backend/src/openpdm/api/core.py tests
```

Expected: changes are limited to ADR/documentation coverage and drift correction.

- [ ] **Step 5: Prepare final maintainer summary**

Summarize:

```markdown
Implemented:

* Proposed ADR-0044, ADR-0045 and ADR-0046 for existing implementation decisions.
* Updated development, deployment and API documentation to match those ADRs.
* Routed plugin orchestration through the composition root.
* Clarified disposable schema initialization versus Alembic deployment migrations.

Verification:

* `uv run pytest -q`
* `uv run python scripts/validate_documentation.py`
* `pnpm run lint`
* `pnpm run test`

Notes:

* ADRs are `Proposed` pending maintainer acceptance.
* No engineering-domain semantics were added to the Platform Core.
```

---

## Self-Review

Spec coverage: the plan covers missing ADR creation, related documentation, plugin boundary drift, schema initialization drift, and verification.

Placeholder scan: the plan contains no unresolved placeholders, no deferred validation steps, and no unspecified test commands.

Type consistency: the planned helper name is consistently `initialize_disposable_database(settings: Settings | None = None) -> None`; plugin orchestration consistently consumes `MODULES` from the composition root.
