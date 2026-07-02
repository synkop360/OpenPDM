# AGENTS.md

> This is the authoritative instruction file for AI coding agents working on OpenPDM.

Before performing any task:

1. Read this file completely.
2. Read the project documentation in the following order:
   - docs/PROJECT_CHARTER.md
   - docs/ARCHITECTURE.md
   - docs/VISION.md
   - ROADMAP.md
3. Follow all accepted ADRs.
4. If documentation conflicts, the highest priority document wins.
5. Never make architectural decisions without proposing a new ADR.

If any instruction is ambiguous, stop and ask for clarification rather than making assumptions.

---

## Session Start Checklist

At the beginning of every new session:

- Read AGENTS.md.
- Read accepted ADRs.
- Identify the Platform Modules impacted by the task.
- Verify that the requested change respects the Platform Core boundaries.
- Explain any architectural concern before writing code.

---

# Official Terminology

Always use the official project terminology.

| Term              | Meaning                                     |
| ----------------- | ------------------------------------------- |
| Platform Core     | Generic business core of OpenPDM.           |
| Platform Modules  | Internal capabilities of the Platform Core. |
| Extension API     | Public extension contract.                  |
| Official Plugins  | Plugins maintained by OpenPDM.              |
| Community Plugins | Third-party plugins.                        |

Do not invent alternative names.

---

# Architectural Rules

Always preserve the following principles.

* The Platform Core is domain-agnostic.
* Engineering knowledge belongs to plugins.
* Platform Modules communicate only through public interfaces.
* Never access another Platform Module's internal implementation.
* Never bypass the Extension API.
* Infrastructure must remain replaceable.
* Respect all accepted ADRs.

When in doubt, prefer architectural consistency over implementation convenience.

---

# Working Rules

Before implementing a feature, determine whether it belongs to:

* the Platform Core;
* a Platform Module;
* an Official Plugin.

If uncertain, stop and explain the ambiguity instead of making assumptions.

Do not introduce architectural changes without proposing a new ADR.

---

# Code Generation

Generate production-ready code.

Prefer:

* simple solutions;
* readable code;
* small modules;
* explicit interfaces;
* low coupling;
* high cohesion.

Avoid unnecessary abstractions.

Avoid premature optimization.

Avoid placeholder implementations.

---

# Module Boundaries

A Platform Module:

* owns a single business responsibility;
* exposes a public interface;
* never exposes its internal implementation.

Communication between modules must always occur through their public interfaces.

---

# Plugins

Official Plugins and Community Plugins use the same Extension API.

Do not introduce privileged APIs for Official Plugins.

Plugins must never depend on another plugin's implementation.

---

# Testing

When appropriate:

* write unit tests;
* write integration tests for interactions between Platform Modules;
* test behavior rather than implementation details.

---

# Documentation

Update documentation whenever a public capability changes.

Do not duplicate information already documented elsewhere.

---

# Pull Requests

Keep changes focused.

One Pull Request should implement one logical change.

Separate:

* refactoring;
* new features;
* dependency updates;
* formatting.

---

# If You Are Unsure

Stop.

Explain the uncertainty.

Describe the available options.

Recommend the simplest solution that respects the project architecture.

Never invent architectural decisions.
