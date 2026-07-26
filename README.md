# OpenPDM

OpenPDM is an open-source Engineering Collaboration Platform for organizing,
versioning, relating and securing Engineering Assets.

This repository snapshot is a lightweight project documentation and planning
package. Historical implementation artifacts for the backend, frontend, desktop
shell, deployment stack, plugins, generated bindings, tests and detailed docs
package have been removed as project hygiene.

## Current Contents

```text
.gitignore          Project-local generated artifact ignores.
AGENTS.md           Coding-agent and architecture guardrails.
CONTRIBUTING.md     Contribution expectations for this cleaned package.
ROADMAP.md          Product capability roadmap.
TASK_TEMPLATE.md    Task planning template.
LICENSE             Apache-2.0 license.
pyproject.toml      Minimal tooling metadata.
uv.lock             Locked tooling environment for the cleaned package.
```

## Project Direction

The project direction remains:

* keep the Platform Core domain-agnostic;
* keep engineering knowledge in plugins;
* expose extensions through the Extension API;
* preserve clear Platform Module boundaries when implementation work resumes;
* document architectural decisions before relying on them as accepted design.

## Validation

This cleaned package no longer contains the previous implementation test suite or
developer scripts. Validate the remaining package with:

```bash
uv run ruff format --check .
uv run ruff check .
```

Implementation tests must be reintroduced with the implementation they exercise.
