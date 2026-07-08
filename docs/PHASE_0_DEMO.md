# Phase 0 Demonstration

This document describes the Phase 0 foundation demonstration path for OpenPDM.
The repository has since progressed into Phase 1+ implementation, but the Phase
0 foundation and local validation workflow remain useful for verifying the
baseline environment.

Phase 0 is complete when a contributor can build, test and run the OpenPDM
foundation locally with a reproducible environment.

## Demonstration Script

From a clean checkout:

1. Read the governing documents:

   ```text
   AGENTS.md
   docs/PROJECT_CHARTER.md
   docs/ARCHITECTURE.md
   docs/VISION.md
   ROADMAP.md
   docs/adr/
   ```

2. Install dependencies:

   ```bash
   python scripts/dev.py install
   ```

3. Validate the repository:

   ```bash
   python scripts/dev.py validate
   ```

4. Run linting:

   ```bash
   python scripts/dev.py lint
   ```

5. Run tests:

   ```bash
   python scripts/dev.py test
   ```

6. Start the backend:

   ```bash
   python scripts/dev.py run-backend
   ```

7. Confirm the foundation endpoint:

   ```bash
   curl http://localhost:8000/foundation
   ```

8. Start the local deployment path:

   ```bash
   python scripts/dev.py compose-up
   ```

9. Confirm the Compose deployment health endpoint:

   ```bash
   curl http://localhost:18000/health
   ```

## Exit Criteria

Phase 0 exit criteria are:

* repository structure is documented;
* accepted ADRs define the Phase 0 technology stack;
* backend FastAPI skeleton starts;
* Web UI skeleton exists and consumes the public API;
* Desktop Client skeleton exists and uses Tauri;
* Docker Compose starts PostgreSQL 18, MinIO and the backend;
* CI validates Python linting, backend tests, frontend tests and project
  automation configuration;
* documentation explains development, deployment and demonstration paths;
* no Phase 1 Platform Core MVP behavior is implemented early.

## Evidence

Evidence for completion is provided by:

* `python scripts/dev.py validate`
* `python scripts/dev.py lint`
* `python scripts/dev.py test`
* CI results for `.github/workflows/ci.yaml`
* successful local startup of `/health` and `/foundation`
