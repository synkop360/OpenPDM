# Public Application API Reference

This reference inventories the public application API implemented by `backend/src/openpdm/api/core.py`. Run the backend and open `/docs` for authoritative OpenAPI request parameters, schemas and response codes.

Except for health, foundation, registration and sign-in, endpoints require an opaque bearer token issued by the local authentication flow.

## Operational Collection Contract

Operational collection endpoints end in `/page` and return `{ "items": [...], "next_cursor": "..." }`. `next_cursor` is `null` on the final page. They use stable opaque keyset cursors, default to 50 items, and accept at most 100. A cursor is valid only for the same collection, authorization scope, filters, sort key and direction that created it. Clients must treat cursors as opaque and start again without a cursor after changing any of those inputs.

The common query parameters are `limit`, `cursor`, `sort` and `direction=asc|desc`. Collection-specific filters are documented by OpenAPI. Sort and filter keys are allowlisted by the owning Platform Module; unsupported values return `400`. The existing unpaged list routes remain available for compatibility.

## Foundation And Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Runtime health check |
| `GET` | `/foundation` | Build and architecture metadata |
| `POST` | `/auth/register` | Register a local user |
| `POST` | `/auth/sign-in` | Create an opaque server-side session |
| `GET` | `/auth/session` | Resolve the current session |
| `POST` | `/auth/sign-out` | Revoke the current session |
| `POST` | `/auth/sessions/{session_id}/revoke` | Revoke one owned session |
| `PUT` | `/platform/administrators/{user_id}` | Grant or revoke Platform Administrator authority |

## Organizations, Projects And Membership

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/organizations` | Create an Organization and initial Owner membership |
| `GET` | `/organizations` | List the actor's Organization memberships |
| `GET` | `/organizations/{organization_id}` | Read an accessible Organization |
| `GET` | `/organizations/{organization_id}/members` | List Organization members |
| `GET` | `/organizations/{organization_id}/members/page` | Page, filter and sort Organization members |
| `POST` | `/organizations/{organization_id}/members` | Add a registered user and role |
| `PATCH` | `/organizations/{organization_id}/members/{membership_id}` | Change an Organization role |
| `DELETE` | `/organizations/{organization_id}/members/{membership_id}` | Remove membership and contained Project access |
| `POST` | `/projects` | Create a Project inside an Organization |
| `GET` | `/organizations/{organization_id}/projects` | List Organization Projects |
| `GET` | `/organizations/{organization_id}/projects/me` | List the actor's Project memberships |
| `GET` | `/projects/{project_id}` | Read an accessible Project |
| `GET` | `/projects/{project_id}/members` | List Project members |
| `GET` | `/projects/{project_id}/members/page` | Page, filter and sort Project members |
| `POST` | `/projects/{project_id}/members` | Assign an Organization member to a Project |
| `PATCH` | `/projects/{project_id}/members/{membership_id}` | Change a Project role |
| `DELETE` | `/projects/{project_id}/members/{membership_id}` | Remove a Project membership |
| `GET` | `/users/me/project-views` | List the actor's private saved Engineering Asset views |
| `POST` | `/users/me/project-views` | Create a private saved Engineering Asset view |
| `GET` | `/users/me/project-views/{view_id}` | Read an owned saved view |
| `PUT` | `/users/me/project-views/{view_id}` | Replace an owned saved view |
| `DELETE` | `/users/me/project-views/{view_id}` | Delete an owned saved view |

Membership addition accepts exactly one of `user_email` or the legacy `user_id`. Roles are `Owner`, `Maintainer`, `Contributor` and `Viewer`. Only Owners manage Owner roles, and every Organization and Project must retain at least one Owner.

Saved Engineering Asset views are owner-private, scoped to one readable Project, and store only allowlisted generic Asset filters, sort configuration, density and selected columns. They are not returned after the owner loses Project access.

## Engineering Assets, Revisions And Blobs

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/assets` | Create a generic Engineering Asset |
| `GET` | `/projects/{project_id}/assets` | List Project Engineering Assets |
| `GET` | `/projects/{project_id}/assets/page` | Page, filter and sort Project Engineering Assets |
| `GET` | `/assets/{asset_id}` | Read an Engineering Asset aggregate |
| `GET` | `/assets/{asset_id}/history` | List immutable Revisions |
| `POST` | `/assets/{asset_id}/revisions` | Create a Revision |
| `POST` | `/revisions/{revision_id}/representations` | Add a Representation |
| `POST` | `/assets/{asset_id}/status` | Change the generic lifecycle status |
| `POST` | `/blobs/uploads` | Upload Blob content |
| `POST` | `/blobs/upload-sessions` | Create a bounded resumable Blob upload session |
| `PUT` | `/blobs/upload-sessions/{session_id}/chunks/{chunk_number}` | Persist one raw `application/octet-stream` chunk |
| `GET` | `/blobs/upload-sessions/{session_id}` | Read authorized upload progress |
| `POST` | `/blobs/upload-sessions/{session_id}/complete` | Verify, assemble, and create the Blob |
| `DELETE` | `/blobs/upload-sessions/{session_id}` | Cancel and clean a resumable upload session |
| `GET` | `/blobs/{blob_id}/download` | Download authorized Blob content |

`POST /blobs/uploads` remains supported for legacy multipart clients. A resumable
session accepts the target `asset_id`, `filename`, `media_type`,
`total_size_bytes`, and an optional
SHA-256 digest. Session views expose progress and the completed Blob, never
provider object locations. Chunks are zero-based, can arrive out of order, and
must meet the returned fixed chunk size except for the final remainder.
Identical retries, completion, and cancellation are idempotent. Every session
operation reauthorizes both the owning user and current write access to the
target Engineering Asset. Completed Blob responses expose client-safe metadata
only: identifier, filename, media type, size, checksum and creation time.

A Representation may claim a completed resumable Blob only for the Engineering
Asset bound to its upload session. Legacy multipart Blobs remain usable by their
creating user, subject to current write permission on the target Engineering
Asset; another user's Blob identifier never grants authority.

## Collaboration And Notifications

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/assets/{asset_id}/collaboration-state` | Read availability and lock state |
| `POST` | `/assets/{asset_id}/checkout` | Acquire an Asset lock |
| `POST` | `/assets/{asset_id}/unlock` | Release or force-release a lock |
| `POST` | `/assets/{asset_id}/checkin` | Create a Revision and release the lock |
| `GET` | `/assets/{asset_id}/timeline` | Read collaboration timeline entries |
| `GET` | `/notifications` | List actor notifications |
| `GET` | `/notifications/page` | Page and filter actor notifications |
| `POST` | `/notifications/read` | Atomically acknowledge selected or all matching notifications |
| `POST` | `/notifications/{notification_id}/read` | Acknowledge a notification |

## Relationships, References And Graph Queries

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/assets/{asset_id}/relationships` | Create an Asset-to-Asset relationship |
| `GET` | `/assets/{asset_id}/relationships` | List all adjacent relationships |
| `GET` | `/assets/{asset_id}/relationships/incoming` | List incoming relationships |
| `GET` | `/assets/{asset_id}/relationships/outgoing` | List outgoing relationships |
| `PUT` | `/relationships/{relationship_id}/metadata` | Replace generic relationship metadata |
| `DELETE` | `/relationships/{relationship_id}` | Delete a relationship |
| `POST` | `/assets/{asset_id}/references` | Create an external or unresolved reference |
| `GET` | `/assets/{asset_id}/references` | List references |
| `POST` | `/references/{reference_id}/resolve` | Resolve a reference into a relationship |
| `DELETE` | `/references/{reference_id}` | Delete a reference |
| `GET` | `/assets/{asset_id}/graph` | Run a bounded graph query |

Graph reads accept `direction`, `max_depth` and optional `target_asset_id`. See [Phase 3 Asset Graph Query Limits](PHASE_3_ASSET_GRAPH_QUERY_LIMITS.md).

## Metadata And Search

| Method | Path | Purpose |
| --- | --- | --- |
| `PUT` | `/metadata/{target_type}/{target_id}` | Upsert generic metadata |
| `GET` | `/metadata/{target_type}/{target_id}` | List generic metadata |
| `GET` | `/search/assets` | Search accessible Engineering Assets |

## Plugin Platform

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/plugins` | List installed plugin lifecycle records |
| `GET` | `/plugins/page` | Page, filter and sort plugin lifecycle records |
| `GET` | `/plugins/{plugin_id}` | Inspect one plugin and its diagnostic state |
| `POST` | `/plugins/packages` | Install a validated plugin package; Platform Administrator only |
| `POST` | `/plugins/{plugin_id}/install` | Promote a compatible discovered package to installed state |
| `PUT` | `/plugins/{plugin_id}/package` | Upgrade a plugin with a same-identity validated package |
| `DELETE` | `/plugins/{plugin_id}` | Remove a disabled plugin lifecycle record and configuration |
| `POST` | `/plugins/{plugin_id}/state` | Enable or disable a plugin; Platform Administrator only |
| `GET` | `/plugins/{plugin_id}/configuration` | Read public configuration and configured secret names |
| `PUT` | `/plugins/{plugin_id}/configuration` | Validate and update deployment configuration; Platform Administrator only |
| `GET` | `/plugins/{plugin_id}/event-deliveries` | Inspect delivery, retry and failure state |
| `POST` | `/plugins/{plugin_id}/providers/metadata` | Invoke a Metadata Provider for one authorized target |
| `POST` | `/plugins/{plugin_id}/providers/assets/{project_id}` | Invoke an Asset Provider within one authorized Project |
| `GET` | `/providers` | Discover running provider plugins and their public capabilities |
| `POST` | `/plugins/{plugin_id}/providers/options` | Retrieve bounded declarative option sets from an Option Provider |

Plugin configuration responses include the bounded declarative `configuration_schema` used to render safe operator controls.

`POST /plugins` remains as a compatibility error route and never installs metadata-only or native code. Package installation accepts `multipart/form-data` with a `package` file plus `plugin_type` and `discover_only` query parameters. Structurally valid incompatible packages receive an inspectable `incompatible` state but cannot be enabled. Authenticated applications discover only running providers through `GET /providers`. Option Providers return bounded text values and labels; they cannot inject HTML, scripts, styles or application components. See [Plugin Development](PLUGIN_DEVELOPMENT.md) and [Plugin Security](PLUGIN_SECURITY.md).

## Errors And Observability

Authorization is enforced by the Platform Core for every protected path. Expected failures use HTTP status codes such as `400`, `403`, `404` and `409`; collaboration failures may include structured recovery context.

Significant mutations write audit records and emit domain events. Successful graph-query audit records are optional through `OPENPDM_AUDIT_GRAPH_QUERIES`; permission denials and security-sensitive failures remain observable.
