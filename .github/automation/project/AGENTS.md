# .github/project/AGENTS.md

# projectctl AI Instructions

These instructions apply only to the projectctl utility.

They intentionally override some architectural expectations of OpenPDM.

OpenPDM is the product.

projectctl is only an internal repository maintenance tool.

Do not apply the full architectural rigor of OpenPDM to projectctl.

---

# Goal

Synchronize GitHub from project.yaml.

Nothing more.

---

# Principles

Prefer:

* procedural code;
* explicit logic;
* simple functions;
* minimal dependencies;
* readability.

Avoid:

* frameworks;
* dependency injection;
* plugin systems;
* layered architectures;
* design patterns without clear value;
* premature abstraction.

---

# Keep It Small

projectctl should remain a small codebase.

If a feature significantly increases complexity, question whether it is truly needed.

The simplest solution that works is preferred.

---

# Source of Truth

Never read GitHub as the authoritative source.

GitHub reflects project.yaml.

project.yaml is authoritative.

---

# Scripts

Each script has one responsibility.

* validate.py validates.
* apply.py synchronizes.
* export.py exports.

Do not merge responsibilities.

---

# Error Handling

Fail fast.

Provide explicit error messages.

Never silently ignore invalid configurations.

---

# GitHub Operations

Operations should be idempotent.

Running apply.py multiple times should always converge to the same GitHub Project.

---

# Future Features

Only implement new functionality when required by OpenPDM.

Do not build generic capabilities for hypothetical future users.

---

# Final Rule

Whenever a design choice exists:

Choose the solution that produces the smallest amount of understandable code.
