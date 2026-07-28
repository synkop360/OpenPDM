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

## Required Manual Checks

Run the browser workflow in [Web UI Manual Test Guide](WEB_UI_MANUAL_TEST_GUIDE.md) for:

* two local browser sessions
* plugin package persistence after backend restart
* one real local file upload and browser download

## Known Limits

* No production high availability.
* No desktop synchronization.
* No desktop notifications.
* No custom workflow engine, approvals or release process.
* No broad CAD integrations.
* No organization-wide shared saved views.
* No engineering-domain semantics in the Platform Core.
