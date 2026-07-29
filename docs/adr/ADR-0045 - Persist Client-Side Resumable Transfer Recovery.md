# ADR-0045 - Persist Client-Side Resumable Transfer Recovery

**Status:** Proposed

---

# Context

ADR-0042 defines storage-independent resumable Blob upload sessions owned by the Blobs Platform Module. The Web UI currently complements that server contract by storing minimal per-user, per-Asset transfer recovery state in browser `sessionStorage`.

The stored client state contains session identity and file identity so an interrupted check-in can resume against the public upload-session API. It does not contain file bytes, object-storage keys, credentials or authority.

This behavior affects user recovery, security expectations and future desktop/browser alignment, but it is not currently captured by an ADR.

---

# Decision

OpenPDM application clients may persist bounded, local transfer recovery state for resumable Blob uploads.

For the Web UI, recovery state is scoped by authenticated user and Engineering Asset, stored in browser `sessionStorage`, and limited to:

* user identifier;
* Asset identifier;
* upload session identifier;
* selected file name, size, media type and last-modified timestamp;
* completed Blob identifier only after server completion succeeds.

Clients must revalidate recovery state with the public application API before reuse. The server remains the authority for upload-session status, ownership, Project authorization, accepted chunks and completed Blob records.

Client recovery state must never include Blob bytes, provider object keys, storage credentials, plugin data, authorization tokens beyond the normal application session mechanism, or engineering-domain semantics.

---

# Consequences

## Positive

* Users can recover interrupted transfers without restarting successful chunks.
* Server-side upload-session ownership and authorization remain authoritative.
* Browser-local recovery stays bounded and avoids storing file contents.
* The Web UI behavior is now documented for future desktop and browser work.

## Trade-offs

* Recovery is limited to the current browser session storage lifetime.
* Clients must handle stale, mismatched or revoked sessions cleanly.
* Broader offline sync or durable desktop transfer queues require a future ADR.

---

# Review

Reconsider this decision when OpenPDM introduces desktop synchronization, offline transfer queues or cross-device transfer recovery.
