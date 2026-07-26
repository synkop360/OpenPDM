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
