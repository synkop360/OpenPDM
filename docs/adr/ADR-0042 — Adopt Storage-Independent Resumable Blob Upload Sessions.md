# ADR-0042 — Adopt Storage-Independent Resumable Blob Upload Sessions

**Status:** Accepted

---

# Context

Engineering files may be too large or networks too unreliable for a single request to complete safely. Retrying a whole upload wastes bandwidth and makes check-in recovery difficult.

ADR-0003 separates Blob content from the immutable Engineering Asset lifecycle. ADR-0006 requires S3-compatible storage behind replaceable infrastructure interfaces and forbids MinIO-specific behavior in Platform Core business logic.

Provider-specific multipart upload contracts would expose infrastructure details to application clients. Creating a Blob before all content is verified would also allow incomplete binary content to enter the lifecycle.

OpenPDM therefore needs resumable upload orchestration that remains owned by the Blobs Platform Module and independent from the configured storage adapter.

---

# Decision

OpenPDM will introduce bounded resumable Blob upload sessions through the public application API and the Blobs Platform Module public interface.

A client creates a session with a filename, media type, total byte size and optional content digest. The platform returns an opaque session identifier, bounded chunk requirements, expiry information and current progress.

Clients upload numbered chunks. Chunk size and session size are bounded by deployment configuration with documented platform limits. Chunks may arrive out of order. Repeating an identical chunk is idempotent; attempting to replace an accepted chunk with different content is rejected.

Every create, upload, inspect, complete and cancel operation is authenticated and authorized against the session's owning user and resource context. Session identifiers do not grant authority.

Completion succeeds only when all required bytes are present and the total size and optional digest match. The Blobs Platform Module creates the completed Blob record only after verification. Repeated completion returns the same completed result. Incomplete or mismatched sessions remain outside the immutable Asset, Revision and Representation lifecycle.

Cancellation and expiry are explicit terminal states. The platform cleans abandoned chunks after expiry and records safe diagnostics without exposing storage locations.

Storage adapters implement session initialization, idempotent chunk persistence, progress inspection, verified assembly and cleanup. They may use provider-specific facilities internally, but the public application API and Platform Module contracts expose no S3, MinIO or provider-specific identifiers.

## Architectural Rules

1. The Blobs Platform Module owns upload-session state, validation and completion.
2. No Blob record is created before size and digest verification succeeds.
3. Storage adapters remain replaceable and hide provider-specific multipart behavior.
4. Every session operation reauthorizes the actor and resource context.
5. Chunk and session limits are bounded and documented.
6. Completion, identical chunk retry and cancellation are idempotent within their documented states.
7. Plugins receive no storage credentials or direct upload-session access through this decision.

---

# Consequences

## Positive

* Interrupted uploads can resume without retransmitting verified chunks.
* Check-in can present truthful progress, cancellation, retry and recovery.
* Incomplete content never becomes an immutable Blob.
* Storage infrastructure remains replaceable.
* Duplicate and out-of-order delivery have explicit behavior.

## Trade-offs

* Session state, expiry and abandoned-chunk cleanup add persistence and operational work.
* Storage adapters require additional capabilities and failure tests.
* Digest verification consumes computation and may require streaming assembly.
* Deployments must choose bounded transfer and retention limits.

These trade-offs are acceptable because reliable large-file transfer is essential for Engineering Assets and must not compromise Blob integrity or infrastructure boundaries.

---

# Alternatives Considered

## Keep Single-Request Uploads Only

Rejected because failed large uploads must restart and cannot provide reliable progress or recovery.

## Expose S3 Multipart Uploads or Presigned Provider URLs

Rejected because application contracts would depend on the active storage provider and could bypass Platform Core authorization.

## Create Incomplete Blob Records

Rejected because it would weaken the immutable lifecycle and require every Blob consumer to understand partial state.

---

# Review

Reconsider this decision if measured deployments do not require resumable transfer, or if the storage-independent adapter contract cannot satisfy objective integrity, performance or self-hosting requirements.
