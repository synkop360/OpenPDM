# OpenPDM Web UI Manual Test Guide

This guide describes how to manually test the current Phase 1 Web UI prototype.

The Web UI is a normal consumer of the public application API. It exercises the
Phase 1 Platform Core through the browser and does not bypass Platform Module
boundaries.

## Scope

This guide covers the implemented prototype workflow for:

* local user registration
* local sign-in and sign-out
* Organization bootstrap
* Project bootstrap
* Engineering Asset creation
* immutable Revision creation through file upload
* Blob-backed file download

This guide does not cover:

* detailed Web UI polish review
* plugin execution
* engineering-specific behavior
* desktop client behavior
* future collaboration or workflow phases

## Platform Modules Touched by This Workflow

The current browser workflow exercises these Platform Modules:

* Organization
* Project
* Assets
* Blobs

It also relies on the public authentication and authorization capabilities
defined for Phase 1.

## Prerequisites

You need:

* Python 3.12+
* `uv`
* Node.js 22+
* `pnpm`

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

The frontend is configured to call:

* `http://127.0.0.1:8000`

through `frontend/.env.development`.

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

### 9. Sign Out

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
* the session survives a browser refresh
* sign-out removes access to the protected workspace
