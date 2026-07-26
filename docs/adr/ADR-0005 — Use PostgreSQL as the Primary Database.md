# ADR-0005 — Use PostgreSQL as the Primary Database

**Status:** Accepted

---

# Context

OpenPDM needs a primary database for generic Platform Core data such as Organizations, Projects, Assets, Revisions, Representations, Metadata, Permissions, Audit records and Events.

The primary database must support reliable transactional behavior, relational integrity and long-term maintainability. It must also support the modular monolith architecture without coupling the Platform Core to infrastructure implementation details.

OpenPDM stores binary content separately from business data, as defined by ADR-0003. The primary database stores business state and references to Blob storage, not the Blob contents themselves.

At the time of this decision, PostgreSQL 18 is a supported stable major version. PostgreSQL 19 is still in beta and is not suitable for production or active development use.

---

# Decision

OpenPDM will use **PostgreSQL 18** as the primary database.

Backend database access will use:

* **SQLAlchemy 2** for ORM and database access;
* **Alembic** for schema migrations.

The Platform Core must depend on application-level interfaces and repository abstractions where appropriate, not directly on PostgreSQL-specific behavior in business logic.

PostgreSQL-specific features may be used only when they provide clear value and do not compromise replaceability of infrastructure or the public contracts of Platform Modules.

---

# Consequences

## Positive

* PostgreSQL provides mature relational storage and transactional guarantees.
* SQLAlchemy 2 provides explicit, modern Python database access patterns.
* Alembic provides a standard migration path.
* PostgreSQL is widely available for self-hosted deployments.
* A relational database fits the early Platform Core model for organizations, projects, assets, revisions, permissions and audit data.

## Trade-offs

* PostgreSQL becomes the default operational dependency for OpenPDM deployments.
* Database migrations require discipline from the beginning of the project.
* Developers need a local PostgreSQL environment or compatible test setup.
* Infrastructure replaceability must be protected through module boundaries and application-level interfaces.

These trade-offs are acceptable because OpenPDM needs reliable transactional storage more than database neutrality at the implementation level.

---

# Alternatives Considered

## SQLite

SQLite was rejected as the primary database because OpenPDM is a collaborative platform and needs a server-grade relational database for concurrent multi-user operation.

## MySQL or MariaDB

MySQL and MariaDB were not selected because PostgreSQL provides a strong open-source default with broad support for relational integrity and advanced querying while remaining self-hostable.

## PostgreSQL 19 Beta

PostgreSQL 19 Beta was rejected because beta releases are not intended for production systems or active development projects.

---

# References

* PostgreSQL versioning policy - https://www.postgresql.org/support/versioning/
* PostgreSQL beta information - https://www.postgresql.org/developer/beta/

---

# Review

This decision should be reconsidered only if PostgreSQL no longer satisfies OpenPDM's persistence requirements or if objective operational constraints require another primary database.
