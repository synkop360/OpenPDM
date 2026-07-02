# ADR-0001 — Adopt a Modular Monolith Architecture

**Status:** Accepted

---

# Context

OpenPDM is designed as an Engineering Collaboration Platform intended to evolve over many years while remaining accessible to individuals, small engineering teams and organizations of all sizes.

Several architectural styles were considered, including:

* Layered Monolith
* Modular Monolith
* Microservices
* Service-Oriented Architecture (SOA)

Although microservices offer deployment flexibility and independent scalability, they introduce significant operational complexity:

* distributed deployments;
* network communication between services;
* distributed transactions;
* service discovery;
* additional monitoring and debugging requirements;
* increased development overhead.

These concerns provide little value during the early stages of OpenPDM and would unnecessarily increase the barrier to contribution.

At the same time, a traditional monolith risks creating strong coupling between business capabilities, making long-term maintenance increasingly difficult.

OpenPDM therefore requires an architecture that combines operational simplicity with strong internal modularity.

---

# Decision

OpenPDM adopts a **Modular Monolith** architecture.

The application is deployed as a single executable process while being internally organized into independent Platform Modules.

Each Platform Module owns a single business responsibility and exposes a well-defined public interface.

Modules communicate exclusively through these public interfaces.

No Platform Module may access the internal implementation of another Platform Module.

The same architectural principles apply to:

* Platform Modules
* Official Plugins
* Community Plugins

The Extension API remains the single supported mechanism for extending the platform.

No privileged internal APIs are introduced for Official Plugins.

---

# Consequences

## Positive

* Simple deployment.
* Simple local development.
* Low operational complexity.
* Strong separation of responsibilities.
* High maintainability.
* Easier automated testing.
* Clear architectural boundaries.
* Extension model validated by the project's own Official Plugins.
* Possibility of extracting modules in the future if justified by real-world requirements.

## Trade-offs

* The entire application is deployed as a single process.
* Individual Platform Modules cannot be scaled independently.
* Architectural discipline is required to preserve module boundaries.

These trade-offs are considered acceptable because OpenPDM prioritizes maintainability, simplicity and contributor experience over premature distribution.

---

# Architectural Rules

The following rules derive from this decision:

1. OpenPDM is deployed as a single application.
2. Platform Modules communicate only through public interfaces.
3. Platform Modules must never access another module's internals.
4. Official Plugins use the same Extension API as Community Plugins.
5. The Platform Core remains independent from engineering domains.
6. Infrastructure technologies must remain replaceable whenever practical.
7. Future extraction of a Platform Module into an independent service must not require changes to its public contract.

---

# Alternatives Considered

## Traditional Monolith

Rejected due to the high risk of tight coupling between business capabilities.

## Microservices

Rejected because the operational complexity outweighs the expected benefits at the current scale of the project.

The architecture intentionally leaves open the possibility of extracting Platform Modules into separate services in the future if objective operational needs arise.

## Service-Oriented Architecture (SOA)

Rejected because it introduces many of the same operational challenges as microservices without providing sufficient advantages for the expected project lifecycle.

---

# Review

This decision should be reconsidered only if objective evidence demonstrates that a Modular Monolith no longer satisfies the operational or architectural needs of OpenPDM.

Premature migration toward distributed services is explicitly discouraged.
