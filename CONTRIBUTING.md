# Contributing to OpenPDM

Thank you for your interest in OpenPDM.

This repository snapshot is a cleaned documentation and planning package. Keep
changes focused, avoid reintroducing generated or local-tooling artifacts, and
update the remaining documentation whenever project direction changes.

## Before You Start

Read:

* `AGENTS.md`
* `README.md`
* `ROADMAP.md`
* `TASK_TEMPLATE.md`

If implementation work resumes, restore or recreate the supporting architecture
documentation, ADRs, tests and developer commands before treating code changes as
production-ready.

## Pull Requests

Every Pull Request should:

* have a clear and focused purpose;
* be limited to one logical change;
* keep unrelated generated files out of the diff;
* update documentation when project scope or workflow changes;
* include meaningful tests when implementation code is present.

## Validation

For the current cleaned package, run:

```bash
uv run ruff format --check .
uv run ruff check .
```

Do not add placeholder tests. Add tests only when they verify behavior that is
present in the repository.

## Commit Messages

Write clear and concise commit messages, for example:

```text
docs: update project roadmap
chore: ignore local tool artifacts
```
