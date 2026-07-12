# OpenPDM Web UI Manual Test Guide

## Primary Navigation

After sign-in, the dark-first responsive Home view greets the user and shows notifications plus available Organizations and Projects. It does not fetch or display Engineering Asset details. Selecting a Project opens `/projects/{project_id}/overview`; routed tabs expose Overview, Assets, Relationships, Collaboration and Members using delivered public APIs.

The sidebar footer opens `/administration/plugins`. Platform Administrators can install or upgrade plugin packages, inspect lifecycle state and diagnostics, load or update deployment-scoped configuration, enable or disable compatible plugins, and remove disabled plugins. Ordinary users receive an explicit access-denied view because Organization and Project roles do not grant platform-wide plugin authority.

At desktop widths, verify the persistent sidebar, compact top bar, Project list and two-column content area. Below the tablet breakpoint, verify that the menu button opens a keyboard-accessible drawer, the scrim and close button dismiss it, and Project tabs remain horizontally usable.

This guide describes how to manually test the current Web UI prototype across
the delivered Platform Core workflow, membership administration, Phase 2 collaboration slice and Phase 3 Asset Graph surface.

The Web UI is a normal consumer of the public application API. It exercises the
Platform Core through the browser and does not bypass Platform Module
boundaries.

## Scope

This guide covers the implemented prototype workflow for:

* local user registration
* local sign-in and sign-out
* Organization bootstrap
* Project bootstrap
* Organization and Project membership administration
* role assignment and access revocation
* Engineering Asset creation
* immutable Revision creation through file upload
* Blob-backed file download
* Asset collaboration state visibility
* Asset checkout and unlock
* check-in with required revision comment
* collaboration timeline visibility
* collaboration conflict feedback in the Web UI
* in-app collaboration notification visibility and read acknowledgment
* relationship, reference and bounded graph exploration

This guide does not cover:

* detailed Web UI polish review
* plugin execution
* engineering-specific behavior
* desktop client behavior
* desktop synchronization or desktop notifications
* future collaboration or workflow phases

## Platform Modules Touched by This Workflow

The current browser workflow exercises these Platform Modules:

* Organization
* Project
* Assets
* Blobs
* Collaboration
* Relationships
* Notifications

It also relies on the public authentication and authorization capabilities
defined for Phase 1.

## Prerequisites

You need:

* Python 3.12+
* `uv`
* Node.js 22+
* `pnpm`
* one small local file to upload
* two browser profiles or two different browsers for multi-user checks

Optional but useful for the multi-user collaboration checks:

* a second local user account

## Verify Membership Administration

1. Register two local users and sign in as the user who owns an Organization and Project.
2. In **Organization members**, add the second registered user by email and assign a role.
3. Confirm the user appears with their display name, email and selected role.
4. In **Project members**, select that Organization member and assign a Project role.
5. Change the Project role and confirm the updated role remains after refresh.
6. Sign in as the second user and confirm the Organization and Project are accessible according to the assigned role.
7. Remove the user from the Organization and confirm their Project membership and access are revoked.
8. Confirm a Maintainer cannot manage an Owner and that the UI reports the last-Owner safeguard when applicable.

Expected result:

* Owners and Maintainers can manage non-Owner memberships;
* only Owners can grant or manage Owner roles;
* Project candidates come from existing Organization members;
* every Organization and Project retains at least one Owner.

Install dependencies:

```bash
python scripts/dev.py install
```

## Start the Backend

From the repository root:

```bash
python scripts/dev.py run-backend
```

Expected result:

* the backend starts on `http://127.0.0.1:8000`
* `http://127.0.0.1:8000/foundation` returns JSON
* `http://127.0.0.1:8000/docs` opens the API documentation

## Start the Web UI

In a second terminal:

```bash
cd frontend
pnpm run dev
```

Expected result:

* the Vite development server starts successfully
* the browser can open the local frontend URL printed by Vite
* the UI header shows `OpenPDM Web UI Prototype`

The frontend is configured to call the backend through `import.meta.env.VITE_API_BASE_URL` when that environment variable is set.

When running the frontend separately from the backend, set:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

before starting the frontend.

Without `VITE_API_BASE_URL`, the Vite development proxy forwards public API
requests to `http://localhost:8000`. This matches the local backend command. To
proxy to the Docker Compose host port instead, start Vite with
`VITE_API_PROXY_TARGET=http://localhost:18000`.

## Test Data Recommendation

Use clearly unique values for each run to avoid confusion.

Suggested pattern:

* user email: `manual-test-<timestamp>@example.com`
* Organization name: `Manual Test Org <timestamp>`
* Project name: `Manual Test Project <timestamp>`
* Engineering Asset name: `Manual Test Asset <timestamp>`

Prepare one small local file for upload, for example:

* a `.txt`
* a `.pdf`
* a small image

For the Phase 2 collaboration checks, prepare:

* `sample-a.txt` for the first check-in
* `sample-b.txt` for a second check-in

## End-to-End Manual Test

### 1. Confirm Initial Anonymous State

1. Open the Web UI in a clean browser tab.
2. If you already have a stored session, click `Sign out` first and reload.

Expected result:

* the page shows the access panel
* `Sign in` and `Register` tabs are visible
* no Organization, Project, or Engineering Asset content is shown yet

Potential artifact to watch for:

* stale session data briefly visible after reload

### 2. Register a Local User

1. Switch to the `Register` tab.
2. Enter:
   * display name
   * email
   * password
3. Submit the form.

Expected result:

* registration succeeds
* the UI signs in automatically
* a status banner confirms account creation
* the session card shows the new user name and email

Potential artifacts to watch for:

* duplicate submission creates confusing error feedback
* the UI remains on the auth form after successful registration

### 3. Create the First Organization

1. In the workspace panel, use `Create your first Organization`.
2. Enter:
   * Organization name
   * slug
3. Submit the form.

Expected result:

* the Organization is created successfully
* it becomes selected automatically
* the Organization card appears in the Organizations list
* the Project bootstrap form appears

Potential artifacts to watch for:

* slug not matching the entered Organization name intent
* the new Organization exists but is not selected

### 4. Create the First Project

1. In the same workspace panel, use `Create the first Project`.
2. Enter:
   * project name
   * optional description
3. Submit the form.

Expected result:

* the Project is created successfully
* it becomes selected automatically
* the Project appears in the Projects list
* the Engineering Asset creation form becomes usable

Potential artifacts to watch for:

* Project list appears empty until a manual refresh
* wrong Project remains selected after creation

### 5. Create a Generic Engineering Asset

1. In the Engineering Assets panel, use `Create a generic Engineering Asset`.
2. Enter:
   * asset name
   * optional description
3. Submit the form.

Expected result:

* the Engineering Asset is created successfully
* it becomes selected automatically
* the detail panel shows the Asset name, description, and status
* the initial status is a generic Phase 1 status such as `draft`

Potential artifacts to watch for:

* asset list updates but detail panel still shows the previous selection
* blank description renders poorly

### 6. Upload a File Into a New Immutable Revision

1. In the detail panel, use `Upload file into a new Revision`.
2. Enter:
   * optional revision comment
   * optional representation name
   * a local file
3. Submit the form.

Expected result:

* the upload succeeds
* a banner confirms a new immutable Revision was created
* the revision timeline gains a new Revision entry
* the Revision shows:
  * revision number
  * optional revision comment
  * Representation name
  * media type
  * Blob filename
* a `Download` button appears for the Representation

Potential artifacts to watch for:

* duplicate Revision cards after upload
* representation name not defaulting correctly from the selected file
* upload succeeds but the revision timeline does not refresh

### 7. Download the Uploaded File

1. Click the `Download` button on the uploaded Representation.

Expected result:

* the browser starts a file download
* the downloaded file name matches the Blob filename shown in the UI
* the UI shows a banner indicating the download started

Potential artifacts to watch for:

* click does nothing
* browser opens a blank tab instead of downloading
* the wrong file name is downloaded

### 8. Verify Session Persistence

1. Refresh the browser tab.

Expected result:

* the session is restored automatically
* the previously selected Organization remains selected
* the previously selected Project remains selected
* the previously selected Engineering Asset remains selected
* the revision timeline still shows the uploaded Revision

Potential artifacts to watch for:

* visible flicker back to the anonymous state before session restore
* stored selections restored inconsistently

### 9. Verify Collaboration State on a Fresh Asset

1. Stay on the selected Engineering Asset detail view.
2. Locate the collaboration state card.

Expected result:

* the collaboration state section is visible
* the Asset shows `available` before checkout
* a `Check out` action is available
* the timeline section is visible even if it is initially short

Potential artifacts to watch for:

* collaboration state missing until a manual reload
* state text visible but action buttons not synchronized with it

### 10. Check Out the Asset

1. Click `Check out`.

Expected result:

* the action succeeds without a page reload
* the collaboration state changes to `locked`
* the current user is shown as the lock owner
* the check-in form remains available
* the timeline gains a lock-related event

Potential artifacts to watch for:

* state stays `available` until a full refresh
* owner identity is missing after checkout
* duplicate lock events appear in the timeline

### 11. Verify Required Comment on Check-In

1. In the check-in form, choose a file but leave the revision comment empty.
2. Submit the form.

Expected result:

* the check-in is rejected
* the UI shows a clear error message
* no partial or empty revision appears in revision history
* the Asset remains locked by the current user

Potential artifacts to watch for:

* upload appears successful before the error is shown
* a revision card appears despite the rejected submission

### 12. Complete a Valid Check-In

1. Enter a non-empty revision comment.
2. Choose `sample-b.txt` or another small file.
3. Submit the check-in form.

Expected result:

* the check-in succeeds
* a new immutable Revision appears in revision history
* the revision comment is visible in the history
* the collaboration state returns to `available`
* the timeline gains revision and check-in completion events

Potential artifacts to watch for:

* the new Revision appears but the lock is not released
* the lock is released but the timeline does not refresh
* the revision comment is missing from the created Revision

### 13. Verify Lock Contention with a Second User

This check uses two browser sessions. If the second user is not already a member
of the same Project, add them through the Organization and Project member panels first.

1. In browser A, sign in as user 1 and check out the Asset.
2. In browser B, sign in as user 2 and open the same Asset.
3. In browser B, attempt to check out the Asset.

Expected result:

* browser B shows the Asset as locked by another user
* browser B cannot check in changes
* the checkout attempt is rejected with clear conflict feedback
* browser A remains the visible lock owner

Potential artifacts to watch for:

* browser B shows `available` until a manual refresh
* conflict feedback is too generic to explain next steps
* browser B is allowed to check out despite the existing lock

### 14. Verify Unlock by the Lock Owner

1. In browser A, while still owning the lock, click `Unlock`.

Expected result:

* the unlock succeeds
* the collaboration state returns to `available`
* browser B sees the refreshed available state after reloading the Asset view
* the timeline gains an unlock event

Potential artifacts to watch for:

* unlock succeeds but browser B still sees a locked state after refresh
* unlock removes the lock but no timeline event is recorded

### 15. Verify In-App Collaboration Notifications

This check uses the same two browser sessions from the collaboration checks.

1. In browser A, perform a collaboration action that should notify other Project members, for example `Check out` or `Unlock`.
2. In browser B, use the notifications panel and click `Refresh`.
3. Confirm a new notification appears for the approved event.
4. In browser B, click `Mark as read` on that notification.

Expected result:

* browser B can see the approved collaboration notification in the Web UI
* the acting user does not receive a duplicate self-notification for the successful action
* the notification stays visible after it is marked as read
* the notification state changes from unread to read without leaving the page

Potential artifacts to watch for:

* notifications appear for the acting user despite the approved actor-exclusion rule
* notifications disappear completely after read instead of remaining visible
* the read action succeeds in the API but the UI does not update
* notifications from another Project appear in the current user view

### 16. Verify Archived-Asset Recovery Feedback

This check is easiest through the public API docs or another admin surface that
can set the Asset status to `archived`.

1. Archive the selected Asset through the public API.
2. Return to the Asset detail view in the Web UI.
3. Attempt a collaboration action such as `Check out` or check-in.

Expected result:

* the action is rejected
* the UI shows explicit archived-asset feedback
* no new Revision is created
* the user is not guided toward unsupported bypass behavior

Potential artifacts to watch for:

* a generic error hides the archived state
* the UI still offers normal collaboration actions after the failure

### 17. Sign Out

1. Click `Sign out`.

Expected result:

* the session is cleared
* the UI returns to the auth screen
* a refresh does not restore the protected workspace

Potential artifacts to watch for:

* stale Organization or Asset cards remain visible after sign-out
* refresh restores a revoked or signed-out session

## Quick Negative Checks

Run these short checks after the main flow:

### Invalid Sign-In

1. Try signing in with the correct email and an incorrect password.

Expected result:

* sign-in is rejected
* the UI stays on the auth screen
* an error message is shown

### Empty-State Recovery

1. Sign in with a user that has no Organizations.

Expected result:

* the Organization bootstrap form is shown
* no stale Project or Engineering Asset content is visible

### Reload During Workspace Use

1. While viewing an Engineering Asset, refresh the page.

Expected result:

* the app restores the session and current selection cleanly
* no duplicate content or broken loading state appears

### Collaboration State Refresh

1. In browser A, check out or unlock the Asset.
2. In browser B, refresh the Asset detail view.

Expected result:

* browser B reflects the latest lock state after refresh
* ownership cues and action availability match the refreshed state

### Notification Refresh

1. In browser A, perform a collaboration action that should notify other Project members.
2. In browser B, click `Refresh` in the notifications panel.

Expected result:

* browser B sees the new notification after refresh
* notification event text matches the approved Phase 2 event scope
* browser A does not receive a self-notification for the same successful action

### Rejected Check-In Recovery

1. Trigger a rejected check-in, for example by omitting the revision comment.
2. Correct the input and submit again.

Expected result:

* the first attempt fails safely
* the UI remains usable without a full workflow restart
* the corrected retry succeeds without creating duplicate revisions

## What to Capture if You See Artifacts

If something looks wrong, capture:

* the exact step number from this guide
* a screenshot
* the browser console errors
* the backend terminal output
* whether the issue happened after reload, sign-in, upload, or download
* whether the issue reproduces consistently

## Known Areas Worth Watching Closely

These are the parts most likely to show visible prototype artifacts:

* session restoration after reload
* automatic selection after creating Organization, Project, or Asset
* refresh of Asset detail and Revision history after upload
* synchronization of collaboration state and action buttons after checkout or unlock
* conflict feedback clarity during multi-user checks
* browser download behavior across browsers
* empty-state transitions between anonymous, first-use, and populated states

## Suggested Smoke Test Pass Criteria

Treat the prototype workflow as passing when all of the following are true:

* a local user can register and sign in
* the user can create an Organization
* the user can create a Project inside that Organization
* the user can create a generic Engineering Asset inside that Project
* the user can upload a file that creates a new immutable Revision
* the user can download the uploaded Blob-backed file
* the user can see collaboration state for the selected Asset
* the user can check out and unlock the Asset through the Web UI
* check-in requires a revision comment and succeeds when valid
* collaboration conflicts are visible and understandable in the Web UI
* collaboration timeline entries refresh after lock and check-in actions
* in-app collaboration notifications are visible and can be marked as read
* Organization and Project members can be added, assigned roles and removed according to Owner safeguards
* relationship and reference information remains distinct in the Asset Graph surface
* the session survives a browser refresh
* sign-out removes access to the protected workspace
