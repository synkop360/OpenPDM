# ADR-0004 — Use Python and FastAPI for the Backend

**Status:** Accepted

---

# Context

OpenPDM needs a backend technology stack that supports the API-first principle, keeps contributor friction low and remains compatible with the modular monolith architecture defined in ADR-0001.

The early project risk is product and architectural complexity, not raw backend performance. The Platform Core must remain domain-agnostic, but the long-term plugin ecosystem should be approachable for contributors and should not require unnecessary operational complexity.

OpenPDM also needs a backend stack that supports:

* REST APIs with OpenAPI documentation;
* automated tests;
* fast local development;
* clear dependency management;
* readable application code;
* modular organization around Platform Modules and Public Module Interfaces.

FastAPI provides native OpenAPI support and is already suitable for production applications when dependency versions are pinned. The FastAPI documentation explicitly recommends pinning the FastAPI version used by an application.

---

# Decision

OpenPDM will use **Python 3.12+** and **FastAPI** for the backend application.

The backend application exposes the public application API using **REST** and **OpenAPI**.

The backend development toolchain will use:

* **uv** for Python packaging and dependency management;
* **pytest** for backend tests;
* **Ruff** for Python linting and formatting.

Backend dependencies must be pinned for reproducible development and deployment.

The backend must preserve the existing architectural decisions:

* OpenPDM remains a modular monolith.
* Platform Modules communicate only through Public Module Interfaces.
* The Platform Core remains independent from engineering domains.
* Plugins extend the platform through the Extension API, not through internal backend implementation details.

---

# Consequences

## Positive

* FastAPI supports the API-first principle through OpenAPI.
* Python lowers contributor friction and supports rapid product iteration.
* Python is a natural fit for future plugin development and engineering automation.
* pytest and Ruff provide a simple, well-known quality baseline.
* uv provides fast and reproducible dependency management.
* The backend remains easy to run inside the Phase 0 development environment.

## Trade-offs

* Python may not provide the same raw performance characteristics as Go or Rust.
* Care is required to preserve strong module boundaries inside a dynamic language.
* Dependency pinning and upgrade discipline are required because FastAPI and its ecosystem evolve quickly.

These trade-offs are acceptable because OpenPDM currently prioritizes architectural clarity, contributor experience and product iteration speed over maximum backend throughput.

---

# Alternatives Considered

## Go

Go was rejected for the initial backend because it would increase friction for Python-oriented plugin and automation contributors while providing performance benefits that are not yet the main project risk.

## Rust

Rust was rejected for the initial backend because it would increase implementation complexity and contributor friction for the Platform Core. Rust may still be appropriate for focused components in the future if objective requirements justify it.

## Django

Django was not selected because OpenPDM primarily needs an API-first backend rather than a traditional server-rendered web application framework.

---

# References

* FastAPI documentation: About FastAPI versions - https://fastapi.tiangolo.com/deployment/versions/

---

# Review

This decision should be reconsidered if the Python backend prevents OpenPDM from meeting objective performance, security or maintainability requirements that cannot be addressed within the modular monolith.
