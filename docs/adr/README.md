# Architecture Decision Records (ADRs)

Architecture Decision Records (ADRs) document the significant architectural decisions made throughout the OpenPDM project.

Their purpose is to preserve the reasoning behind important decisions, allowing future contributors to understand **why** a choice was made—not just **what** was implemented.

## When to create an ADR

Create an ADR when a decision has a long-term impact on the project.

Typical examples include:

* Architectural patterns
* Public APIs
* Extension mechanisms
* Persistence strategies
* Security models
* Technology adoption or replacement
* Decisions that are difficult or costly to reverse

Minor implementation details should **not** become ADRs.

## ADR Format

Each ADR follows the same structure:

```text
Status

Context

Decision

Consequences
```

Additional sections (Alternatives, References, Review, etc.) may be added when they improve clarity.

## Lifecycle

An ADR progresses through the following states:

* Proposed
* Accepted
* Superseded
* Deprecated

Accepted ADRs are considered part of the project's architecture.

They should only be modified if a new ADR explicitly supersedes them.

## File Naming

Files are numbered sequentially.

Example:

```text
0001-adopt-modular-monolith.md
0002-extension-api.md
0003-asset-model.md
```

Numbers are never reused.

## Guiding Principle

An ADR records a decision—not a discussion.

It should remain concise, easy to read and understandable years after it was written.

## Current ADRs

Recent ADRs:

* ADR-0044 - Adopt The Web UI Operational Interaction Stack
* ADR-0045 - Persist Client-Side Resumable Transfer Recovery
* ADR-0046 - Define Schema Initialization And Migration Discipline
* ADR-0047 - Authorize Bounded Representation Analysis Inputs (Accepted)
* ADR-0048 - Accept Provider Analysis Contributions (Accepted)
* ADR-0049 - Set Analysis Provider Sandbox Fuel Budget (Accepted)
* ADR-0050 - Adopt Asset-Addressable Deep-Linking URL Scheme

## Phase 5 Analysis Decisions

The accepted Phase 5 decisions define a generic Extension API capability, not a
CAD-specific Platform Core contract:

* [ADR-0047](ADR-0047%20-%20Authorize%20Bounded%20Representation%20Analysis%20Inputs.md)
  authorizes one read-authorized Representation with a 5 MiB decoded-content
  boundary.
* [ADR-0048](ADR-0048%20-%20Accept%20Provider%20Analysis%20Contributions.md)
  permits idempotent generic metadata, Reference, and explicitly mapped
  relationship contributions.
* [ADR-0049](ADR-0049%20-%20Set%20Analysis%20Provider%20Sandbox%20Fuel%20Budget.md)
  configures the bounded analysis-provider sandbox fuel budget independently of
  other provider invocations.
