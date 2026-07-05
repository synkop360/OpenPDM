# OpenPDM Development

This document describes the Phase 0 development workflow.

The authoritative architecture remains:

* `docs/PROJECT_CHARTER.md`
* `docs/ARCHITECTURE.md`
* accepted ADRs in `docs/adr/`

## Required Tools

Use these versions or newer compatible versions:

* Python 3.12+
* uv
* Docker
* Node.js 22+ and pnpm for Web UI work
* Rust and Tauri 2 prerequisites only if you are explicitly working on the
  deferred Desktop Client track

## Install Dependencies

```bash
python scripts/dev.py install
```

This installs Python dependencies with uv. If pnpm is available, it also installs
frontend and desktop JavaScript dependencies.

The desktop workspace remains in the repository for future development, but it is
not on the critical path for the current v1 collaboration scope.

## Validate Locally

```bash
python scripts/dev.py validate
python scripts/dev.py lint
python scripts/dev.py test
```

Validation includes:

* Phase 0 repository structure checks;
* GitHub Project configuration validation;
* Ruff formatting and lint checks;
* pytest backend and architecture tests;
* frontend TypeScript and Vitest checks when JavaScript dependencies are installed.

## Run the Backend

```bash
python scripts/dev.py run-backend
```

The Phase 0 API is available at:

* `http://localhost:8000/health`
* `http://localhost:8000/foundation`
* `http://localhost:8000/docs`

## Run the Web UI

```bash
cd frontend
pnpm run dev
```

The Web UI is an API consumer. It must not bypass the public application API or
call Platform Module internals.

## Run the Desktop Client

```bash
cd desktop
pnpm run dev
```

The Desktop Client is also an API consumer. It is currently a deferred track and
is not required to deliver the approved v1 collaboration scope.

Desktop-specific collaboration behavior remains out of scope for the current
Phase 2 delivery, including:

* desktop synchronization;
* desktop notifications;
* local file conflict handling;
* any collaboration behavior that bypasses the public application API.

## Architecture Boundaries

Phase 0 establishes structure without implementing Platform Core business
capabilities.

Rules:

* Platform Modules expose Public Module Interfaces.
* Platform Modules do not access another module's internals.
* Plugins depend on the Extension API, not Public Module Interfaces.
* Infrastructure adapters remain replaceable.
* Engineering-domain knowledge belongs to plugins, not the Platform Core.

Asset lifecycle behavior starts in Phase 1. Plugin lifecycle behavior starts in
later roadmap phases.

