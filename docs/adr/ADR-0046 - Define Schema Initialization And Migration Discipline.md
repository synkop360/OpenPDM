# ADR-0046 - Define Schema Initialization And Migration Discipline

**Status:** Proposed

---

# Context

ADR-0005 selects PostgreSQL as the primary database and Alembic for schema migrations. The current deployment backend runs `alembic upgrade head` before starting the API, while local and test code can create the current SQLAlchemy schema directly.

Direct metadata creation is useful for isolated tests and fast local prototypes, but it can blur production expectations if application startup is treated as a migration mechanism. OpenPDM needs a clear rule that preserves Alembic discipline without making tests unnecessarily slow.

---

# Decision

OpenPDM uses Alembic as the authoritative schema migration mechanism for persistent deployments.

Direct SQLAlchemy metadata creation is allowed only for development and automated test contexts that create disposable databases. The helper name and documentation must make that limited scope explicit.

The backend application must not rely on direct metadata creation as the production schema upgrade path. Deployment entrypoints must run Alembic migrations before serving traffic. Tests may continue to exercise direct disposable schema creation when the test's purpose is not migration behavior.

When a new persistent table, column, constraint or index is introduced, the change must include an Alembic migration and a focused upgrade test when practical.

---

# Consequences

## Positive

* Persistent deployments have one authoritative migration path.
* Fast disposable test setup remains available.
* Future schema changes are less likely to exist only in SQLAlchemy models.
* The implementation aligns more clearly with ADR-0005.

## Trade-offs

* Startup code must distinguish deployment readiness from disposable test initialization.
* Contributors must maintain migrations even when model changes appear simple.
* Existing local databases may require explicit migration commands.

---

# Review

Reconsider this decision if OpenPDM replaces Alembic, introduces a separate migration service, or adopts a different persistence model.
