# ADR-0050 - Adopt Asset-Addressable Deep-Linking URL Scheme

**Status:** Proposed

---

# Context

ADR-0044 established React Router as the Web UI's durable routing mechanism.
`frontend/src/app/routes.ts`'s `parseAppRoute` currently recognizes `/`,
`/notifications`, `/projects`, `/projects/:id/:tab`, and
`/administration/plugins`, parsing them into an `AppRoute` (`view`,
`projectId`, `projectTab`). It did not decide a URL grammar for addressing an
individual resource within a Project.

Today, selecting an Engineering Asset only updates `selectedAssetId` in React
state, persisted to `localStorage` (`frontend/src/app/storage.ts`), and is
never reflected in the URL — unlike the selected Organization and Project,
which are already synced with the route (`App.tsx:434-437`). A user cannot
bookmark, share, or refresh their way back to a specific Engineering Asset;
the URL is identical for every asset in a Project's Assets tab.

Extending the grammar is only useful if the resulting URLs are actually
reachable by a hard navigation, not only by client-side `navigate()` calls.
That is not true today for the grammar that already exists: the Vite
dev-server proxy (`frontend/vite.config.ts:12-17`) forwards every path prefix
in `frontend/src/apiRoutes.ts`'s `API_PROXY_PATHS` — including `/projects`
and `/assets` — straight to the backend at `VITE_API_PROXY_TARGET`. Because
the SPA's own client routes live under those same prefixes, any full-page
load of such a URL (hard refresh, bookmark, shared link, direct navigation)
is proxied to the backend instead of served the SPA shell, and the backend
returns its own JSON 404 for path shapes its routes don't recognize
(confirmed reproducible: `GET /projects/{id}/assets` returns
`{"detail":"Not Found"}`).

A second, related manifestation of the same collision already causes a
visible defect: `API_PROXY_PATHS` has no `/users` entry, but
`listProjectAssetViews` (`frontend/src/api.ts:1010`) calls
`GET /users/me/project-views`. Unproxied, Vite serves `index.html` for that
path; the frontend's content-type check (`frontend/src/api.ts:363-370`) then
raises a routing-error message that surfaces to users verbatim as "Saved
views unavailable: OpenPDM API routing error: expected JSON but received
text/html" (`App.tsx:2949`).

A restructuring of the Asset detail page into tabs is planned as follow-on
work. The grammar decided here needs to accommodate that without requiring a
second grammar-extending ADR immediately after.

---

# Decision

OpenPDM's Web UI adopts a URL grammar that addresses an Engineering Asset as
a path segment nested under its Project and tab, and fixes the dev-server
proxy so that path collisions between SPA routes and the public application
API resolve in the SPA's favor for browser navigations.

Concretely:

1. `frontend/src/app/routes.ts`'s `AppRoute` gains an `assetId: string | null`
   field. `parseAppRoute` recognizes `/projects/:id/:tab/:assetId` for every
   existing `projectTab` value (`overview`, `assets`, `relationships`,
   `collaboration`, `members`), not only `assets` — so a later tab
   restructuring of the Asset detail page can rely on the asset segment
   already being present under any tab, without a further grammar change. A
   tab with no notion of "the selected asset" simply ignores the segment.
2. `App.tsx` treats the URL as the source of truth for the selected
   Engineering Asset the same way it already does for the selected Project:
   `selectedAssetId` is derived from `parseAppRoute` on every route change,
   and the asset-selection `navigate()` calls include the asset segment.
   `localStorage` (`app/storage.ts`) remains a fallback only, used to restore
   the last-viewed asset when a URL carries a Project but no asset segment
   (e.g. first load of `/projects/:id/assets`) — never as the primary source
   once a URL specifies an asset.
3. `frontend/vite.config.ts`'s dev-server proxy changes so that, for every
   proxied path prefix, a request whose `Accept` header indicates a browser
   page navigation (`text/html`) is not proxied to the backend and instead
   falls through to Vite's own SPA `index.html` handling, while `fetch()`/XHR
   calls (which do not send an HTML-accepting `Accept` header) continue to be
   proxied to the backend exactly as today. This uses `http-proxy`'s existing
   per-entry `bypass` option, already available through Vite's
   `server.proxy` configuration — no new dependency. This applies to
   `server.proxy` only; `preview.proxy` (already empty) and the backend's
   public API surface are unchanged.
4. `frontend/src/apiRoutes.ts`'s `API_PROXY_PATHS` gains a `/users` entry,
   closing the second manifestation of the same collision class (the "Saved
   views unavailable" error) as part of the same fix.

This decision governs only the Web UI's client-side routing and its local
development proxy. The Web UI continues to consume only the public
application API; no Platform Module, Platform Core, or Extension API
contract changes as a result.

---

# Consequences

## Positive

* Engineering Assets become bookmarkable, shareable, and survive a page
  refresh, matching the existing behavior for Organizations and Projects.
* The `/projects/{id}/assets` raw-JSON-404 regression (confirmed reproducible
  today) is fixed for every colliding path prefix at once, not patched
  path-by-path.
* The "Saved views unavailable" error disappears as a side effect of the
  same fix, rather than needing its own patch.
* The URL grammar is decided once, before the planned Asset-detail-page tab
  restructuring, so that work does not need to reopen this decision.

## Trade-offs

* The dev-server proxy configuration becomes slightly more complex (a
  `bypass` function per entry instead of a flat string target), which future
  contributors adding a new `API_PROXY_PATHS` entry need to understand rather
  than copy blindly.
* `localStorage`-based asset recall is now explicitly a fallback, not a
  feature in its own right — a user who lands on `/projects/:id/assets` with
  no prior selection and no asset segment sees no asset selected until they
  choose one, rather than always resuming their last one. This is judged an
  acceptable, minor behavior change in exchange for the URL being
  authoritative.
* This decision does not address production or preview proxy/hosting
  configuration; if a deployed environment serves the Web UI and API from the
  same origin in a way that reproduces this collision, that is out of scope
  here and would need its own review.

---

# Alternatives Considered

## Query Parameter For The Selected Asset (`?asset=id`)

Rejected because it's inconsistent with how the Organization and Project are
already addressed as path segments (`/projects/:id/:tab`), and because a
query parameter is more easily dropped or mangled by copy/paste, email
clients, and chat tools than a path segment, undermining the sharing use case
this decision exists to serve.

## Leave Asset Selection LocalStorage-Only (No Deep-Linking)

Rejected because it leaves the concrete problem unsolved — Engineering
Assets remain unbookmarkable and unshareable — and does nothing to fix the
underlying proxy collision, which is a real, reproducible defect independent
of whether asset deep-linking is added.

## Move The Public API Behind An `/api` Prefix To Eliminate The Collision

Rejected for this decision: it would remove the path collision at its root,
but it changes the backend's public API surface (documented today as bare
paths like `/health`, `/foundation`, `/projects`) and every existing API
consumer, which is a larger, separate architectural change requiring its own
review — not a Web UI routing decision. The proxy `bypass` approach solves
the same symptom within the Web UI's existing boundary.

---

# References

* ADR-0044 - Adopt The Web UI Operational Interaction Stack

---

# Review

Revisit this decision if a production or preview deployment is found to
reproduce the same SPA/API path collision (this decision only fixes the
local development proxy), or if the planned Asset-detail-page tab
restructuring finds the per-tab asset segment insufficient (e.g. a tab needs
to address more than one asset at once).
