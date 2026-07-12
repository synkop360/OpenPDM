# Public Application API Reference

This reference inventories the public application API implemented by `backend/src/openpdm/api/core.py`. Run the backend and open `/docs` for authoritative OpenAPI request parameters, schemas and response codes.

Except for health, foundation, registration and sign-in, endpoints require an opaque bearer token issued by the local authentication flow.

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
| `POST` | `/organizations/{organization_id}/members` | Add a registered user and role |
| `PATCH` | `/organizations/{organization_id}/members/{membership_id}` | Change an Organization role |
| `DELETE` | `/organizations/{organization_id}/members/{membership_id}` | Remove membership and contained Project access |
| `POST` | `/projects` | Create a Project inside an Organization |
| `GET` | `/organizations/{organization_id}/projects` | List Organization Projects |
| `GET` | `/organizations/{organization_id}/projects/me` | List the actor's Project memberships |
| `GET` | `/projects/{project_id}` | Read an accessible Project |
| `GET` | `/projects/{project_id}/members` | List Project members |
| `POST` | `/projects/{project_id}/members` | Assign an Organization member to a Project |
| `PATCH` | `/projects/{project_id}/members/{membership_id}` | Change a Project role |
| `DELETE` | `/projects/{project_id}/members/{membership_id}` | Remove a Project membership |

Membership addition accepts exactly one of `user_email` or the legacy `user_id`. Roles are `Owner`, `Maintainer`, `Contributor` and `Viewer`. Only Owners manage Owner roles, and every Organization and Project must retain at least one Owner.

## Engineering Assets, Revisions And Blobs

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/assets` | Create a generic Engineering Asset |
| `GET` | `/projects/{project_id}/assets` | List Project Engineering Assets |
| `GET` | `/assets/{asset_id}` | Read an Engineering Asset aggregate |
| `GET` | `/assets/{asset_id}/history` | List immutable Revisions |
| `POST` | `/assets/{asset_id}/revisions` | Create a Revision |
| `POST` | `/revisions/{revision_id}/representations` | Add a Representation |
| `POST` | `/assets/{asset_id}/status` | Change the generic lifecycle status |
| `POST` | `/blobs/uploads` | Upload Blob content |
| `GET` | `/blobs/{blob_id}/download` | Download authorized Blob content |

## Collaboration And Notifications

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/assets/{asset_id}/collaboration-state` | Read availability and lock state |
| `POST` | `/assets/{asset_id}/checkout` | Acquire an Asset lock |
| `POST` | `/assets/{asset_id}/unlock` | Release or force-release a lock |
| `POST` | `/assets/{asset_id}/checkin` | Create a Revision and release the lock |
| `GET` | `/assets/{asset_id}/timeline` | Read collaboration timeline entries |
| `GET` | `/notifications` | List actor notifications |
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

`POST /plugins` remains as a compatibility error route and never installs metadata-only or native code. Package installation accepts `multipart/form-data` with a `package` file plus `plugin_type` and `discover_only` query parameters. Structurally valid incompatible packages receive an inspectable `incompatible` state but cannot be enabled. See [Plugin Development](PLUGIN_DEVELOPMENT.md) and [Plugin Security](PLUGIN_SECURITY.md).

## Errors And Observability

Authorization is enforced by the Platform Core for every protected path. Expected failures use HTTP status codes such as `400`, `403`, `404` and `409`; collaboration failures may include structured recovery context.

Significant mutations write audit records and emit domain events. Successful graph-query audit records are optional through `OPENPDM_AUDIT_GRAPH_QUERIES`; permission denials and security-sensitive failures remain observable.
