# OpenPDM

OpenPDM is an open-source Engineering Collaboration Platform for organizing,
versioning, relating and securing Engineering Assets.

The project is in **Phase 0 - Foundation**. This phase establishes the technical
foundation only: repository structure, development environment, CI, architecture
skeleton, local deployment and initial documentation.

Phase 0 intentionally does not implement Platform Core MVP behavior such as
Assets, Revisions, authentication, permissions, search or plugin runtime
capabilities. Those belong to later roadmap phases.

## Quickstart

Required tools:

* Python 3.12+
* uv
* Docker
* Node.js 22+ and pnpm for frontend work
* Rust and the Tauri prerequisites for desktop work

Install dependencies:

```bash
python scripts/dev.py install
```

Validate the repository:

```bash
python scripts/dev.py validate
python scripts/dev.py lint
python scripts/dev.py test
```

Run the backend API locally:

```bash
python scripts/dev.py run-backend
```

Start the local deployment environment:

```bash
python scripts/dev.py compose-up
```

The Phase 0 backend exposes:

* `GET /health`
* `GET /foundation`
* OpenAPI documentation at `/docs`

## Repository Structure

```text
backend/      FastAPI modular monolith backend skeleton.
frontend/     React, TypeScript and Vite Web UI skeleton.
desktop/      Tauri desktop client skeleton.
deployment/   Local Docker Compose deployment.
docs/         Project documentation and ADRs.
scripts/      Developer validation and command helpers.
tests/        Repository-level architecture boundary tests.
```

## Authoritative Documentation

Before contributing, read these documents in order:

1. `AGENTS.md`
2. `docs/PROJECT_CHARTER.md`
3. `docs/ARCHITECTURE.md`
4. `docs/VISION.md`
5. `ROADMAP.md`
6. Accepted ADRs in `docs/adr/`

Useful Phase 0 guides:

* `docs/DEVELOPMENT.md`
* `docs/DEPLOYMENT.md`
* `docs/INTERNAL_FUNCTIONING.md`
* `docs/PHASE_0_DEMO.md`

