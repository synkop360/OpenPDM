# AGENTS.md

> This is the authoritative instruction file for AI coding agents working on
> OpenPDM.

Before performing any task:

1. Read this file completely.
2. Read the remaining project documentation:
   - `README.md`
   - `ROADMAP.md`
   - `TASK_TEMPLATE.md`
3. Preserve the project terminology and architectural intent below.
4. Do not invent architectural decisions. If implementation work resumes, create
   or restore ADR coverage before relying on new architecture as accepted.

If any instruction is ambiguous, stop and ask for clarification rather than
making assumptions.

---

## Official Terminology

Always use the official project terminology.

| Term | Meaning |
| --- | --- |
| Platform Core | Generic business core of OpenPDM. |
| Platform Modules | Internal capabilities of the Platform Core. |
| Extension API | Public extension contract. |
| Official Plugins | Plugins maintained by OpenPDM. |
| Community Plugins | Third-party plugins. |
| Engineering Asset | User-facing meaning of the Core Asset. |

Do not invent alternative names.

---

## Architectural Intent

Preserve these principles when implementation work resumes:

* The Platform Core is domain-agnostic.
* Engineering knowledge belongs to plugins.
* Platform Modules communicate only through public interfaces.
* Never access another Platform Module's internal implementation.
* Never bypass the Extension API.
* Infrastructure must remain replaceable.
* Official Plugins and Community Plugins use the same Extension API.

---

## Working Rules

Before implementing a feature, determine whether it belongs to:

* the Platform Core;
* a Platform Module;
* an Official Plugin.

If uncertain, stop and explain the ambiguity instead of making assumptions.

Do not introduce architectural changes without proposing documentation for the
decision first.

---

## Testing

Do not add placeholder tests. Tests should verify behavior that exists in the
repository. If implementation code is absent, report that implementation tests
are not applicable instead of creating tests that do nothing.

---

## Pull Requests

Keep changes focused.

One Pull Request should implement one logical change.

Separate:

* refactoring;
* new features;
* dependency updates;
* formatting;
* generated artifact cleanup.
