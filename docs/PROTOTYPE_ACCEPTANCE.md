# Usable Prototype Acceptance

This guide defines the usable prototype gate for OpenPDM.

The prototype supports a local team workflow for generic Engineering Asset
collaboration. It does not add engineering-domain semantics to the Platform
Core.

## Supported Workflow

1. Start PostgreSQL, MinIO, backend and Web UI from the documented local commands.
2. Register two local users.
3. Create an Organization and Project.
4. Create a generic Engineering Asset.
5. Upload and download a Blob-backed file Revision.
6. Check out, check in and unlock the Engineering Asset.
7. Review Revision history, timeline events and notifications.
8. Create and inspect generic relationships and references.
9. Install, enable, invoke and disable the dummy categories plugin through Plugin Administration.

## Required Automated Checks

Run from the repository root:

```powershell
uv run pytest
pnpm.cmd --dir frontend test
pnpm.cmd --dir frontend build
pnpm.cmd --dir frontend test:e2e
uv run python .github/automation/project/validate.py .github/automation/project/project.yaml
uv run python scripts/validate_phase0.py
uv run python scripts/validate_documentation.py
```

The browser gate covers first-run local user registration, Organization and
Project creation, generic Engineering Asset creation, check-out/check-in,
Revision history, Blob-backed browser download, two-user collaboration conflict
feedback, in-app notification acknowledgment, and distinct Incoming, Outgoing
and References Asset Graph inspection without bulk mutation controls. It also
covers the generic dummy categories plugin demonstration: Platform Administrator
review, lifecycle enable/disable, provider discovery, text-only options,
metadata contribution, and provider disappearance after disablement while prior
metadata remains.

## Required Manual Checks

Run the browser workflow in [Web UI Manual Test Guide](WEB_UI_MANUAL_TEST_GUIDE.md) for:

* two local browser sessions
* plugin package persistence after backend restart
* one real local file upload and browser download

## Latest Prototype Acceptance Result

Date: 2026-07-29
Scope: automated local prototype gate and validated manual local-service smoke
checks covering startup readiness, first-run workspace setup, generic
Engineering Asset revision upload/download, two-user collaboration,
notifications, Asset Graph inspection, and the dummy categories plugin provider
journey.
Result: Pass.
Evidence:

* `uv run pytest`: 90 passed, 4 skipped.
* `pnpm.cmd --dir frontend test`: 53 passed.
* `pnpm.cmd --dir frontend build`: passed.
* `pnpm.cmd --dir frontend test:e2e`: 63 passed.
* `uv run python .github/automation/project/validate.py .github/automation/project/project.yaml`: passed.
* `uv run python scripts/validate_phase0.py`: passed.
* `uv run python scripts/validate_documentation.py`: passed.
* `git diff --check`: passed.
* Maintainer-validated manual local-service smoke checks completed:
  * two local browser sessions;
  * plugin package persistence after backend restart;
  * one real local file upload and browser download.

## Phase 5 Mechanical Plugin Acceptance Result

Date: 2026-07-29
Scope: the `org.openpdm.freecad` Official Plugin package, its bounded generic
analysis-provider workflow, and existing-provider regression coverage.
Result: Incomplete.

The focused FreeCAD, generic analysis-provider, reference-plugin, and dummy
categories-plugin checks passed (26 tests), as did the frontend lint, test,
build, desktop Chromium browser, documentation, and project-validation gates.
The built package was validated without starting FreeCAD or another CAD
program. The required manual local-service smoke check is pending and is
defined in [the Phase 5 workflow guide](PHASE_5_FREECAD_PLUGIN.md#pending-manual-local-service-smoke-check).

The repository-wide backend suite has two migration-upgrade failures caused by
duplicate `analysis_contribution_id` column creation, and the repository-wide
Ruff scope includes existing generated binding findings. These must be resolved
before Phase 5 is recorded as fully accepted. The complete matrix and exact
command results are in [the Phase 5 workflow guide](PHASE_5_FREECAD_PLUGIN.md#phase-5-acceptance-matrix).

## Known Limits

* No production high availability.
* No desktop synchronization.
* No desktop notifications.
* No custom workflow engine, approvals or release process.
* No broad CAD integrations.
* No organization-wide shared saved views.
* No engineering-domain semantics in the Platform Core.
