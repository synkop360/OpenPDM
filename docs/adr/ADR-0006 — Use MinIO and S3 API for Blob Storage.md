# ADR-0006 — Use MinIO and S3 API for Blob Storage

**Status:** Accepted

---

# Context

ADR-0003 defines Blob as binary content stored independently from the Asset lifecycle model.

OpenPDM must manage engineering files without making the Platform Core understand engineering file formats. Binary storage must therefore be separated from business data stored in the primary database.

The project also needs a local development and self-hosted deployment path that does not depend on a proprietary cloud provider.

An S3-compatible API gives OpenPDM a widely understood object storage contract while allowing multiple infrastructure implementations.

---

# Decision

OpenPDM will use **S3-compatible object storage** for Blob storage.

The default local and self-hosted implementation will be **MinIO**.

The Platform Core stores Blob metadata and references in the primary database, but Blob binary content is stored in S3-compatible object storage.

Blob storage access must be isolated behind infrastructure-facing application interfaces. Platform Modules must not depend directly on MinIO-specific implementation details.

---

# Consequences

## Positive

* Blob content is separated from the Asset, Revision and Representation model.
* MinIO provides a self-hostable local development and deployment option.
* The S3 API keeps Blob storage infrastructure replaceable.
* Large binary content does not need to be stored inside the primary relational database.
* The decision supports future cloud or on-premises object storage options.

## Trade-offs

* OpenPDM deployments require object storage in addition to the primary database.
* Blob lifecycle management must handle consistency between database records and object storage.
* Local development requires MinIO or another compatible object storage service.
* S3 API behavior must be tested through the application's storage interface, not through provider-specific assumptions.

These trade-offs are acceptable because engineering assets commonly involve large binary files, and separating Blob storage is central to the OpenPDM architecture.

---

# Alternatives Considered

## Store Blobs in PostgreSQL

Storing Blob contents in PostgreSQL was rejected because it couples large binary storage to the primary relational database and conflicts with the intended separation between business data and Blob content.

## Local Filesystem Storage Only

Local filesystem storage was rejected as the primary Blob storage contract because it is harder to scale, secure and replace across deployments. It may still be useful as a test adapter.

## Cloud-Specific Object Storage

A cloud-provider-specific object storage API was rejected because OpenPDM is self-hosted by default and must remain vendor-neutral.

---

# Review

This decision should be reconsidered if S3-compatible storage no longer meets OpenPDM's Blob storage requirements or if a simpler storage contract can satisfy self-hosted, scalable and replaceable deployments.
