# Contributing to OpenPDM

First of all, thank you for your interest in OpenPDM.

Whether you are fixing a typo, reporting a bug, improving the documentation or contributing code, every contribution is appreciated.

Our goal is to build a modern, maintainable and community-driven Engineering Collaboration Platform.

---

# Before You Start

Before contributing, please read:

* `docs/VISION.md`
* `docs/PROJECT_CHARTER.md`
* `docs/ARCHITECTURE.md`

These documents describe the project's long-term direction and architectural principles.

---

# Guiding Principles

When contributing, always aim to:

* Keep the Platform Core generic.
* Preserve module boundaries.
* Prefer simple solutions over clever ones.
* Prioritize readability and maintainability.
* Respect existing architectural decisions.
* Document significant changes.

If a contribution requires changing the architecture, create or update an ADR before implementation.

---

# Reporting Issues

Before opening an issue:

* Search for existing issues.
* Clearly describe the problem.
* Include reproduction steps when applicable.
* Explain the expected behavior.

Feature requests should describe the problem they solve rather than a specific implementation.

---

# Pull Requests

Every Pull Request should:

* Have a clear and focused purpose.
* Be limited to a single logical change.
* Include tests when appropriate.
* Update documentation when necessary.
* Keep unrelated changes out of the same PR.

Small, incremental Pull Requests are preferred over large ones.

---

# Architecture

OpenPDM follows a modular architecture.

When contributing:

* Do not introduce unnecessary coupling between Platform Modules.
* Use public interfaces to communicate between modules.
* Do not bypass the Extension API.
* Do not introduce engineering-specific concepts into the Platform Core.

When in doubt, prioritize architectural consistency over implementation convenience.

---

# Coding Style

Follow the conventions already used in the project.

Consistency is more important than personal preference.

If a new convention is required, discuss it before applying it across the project.

For Phase 0:

* Python code is formatted and linted with Ruff.
* Backend tests use pytest.
* Frontend tests use Vitest.
* The Web UI and Desktop Client consume public APIs only.
* Platform Modules must communicate through Public Module Interfaces.
* The Platform Core must not contain engineering-domain behavior.

Run local validation before opening a pull request:

```bash
python scripts/dev.py validate
python scripts/dev.py lint
python scripts/dev.py test
```

---

# Commit Messages

Write clear and concise commit messages.

Examples:

```text
feat(asset): add revision creation

fix(workflow): prevent duplicate transitions

docs: update architecture diagrams

refactor(search): simplify query builder
```

---

# Code Reviews

Code reviews are collaborative discussions.

Review the code, not the contributor.

Feedback should be:

* respectful;
* constructive;
* technically justified.

The goal is to improve the project together.

---

# Questions

If you are unsure about a design decision, ask before implementing it.

Early discussions are encouraged and usually save time for everyone.

---

# Our Philosophy

OpenPDM values:

* Simplicity
* Maintainability
* Extensibility
* Transparency
* Long-term thinking

Every contribution should move the project toward these goals.
