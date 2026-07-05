# ADR-0025 - Define Notification Acknowledgment and Targeting for Phase 2

**Status:** Accepted

---

# Context

ADR-0021 defines the approved collaboration notification events and restricts
Phase 2 to in-app delivery only. Phase 2 still needs explicit rules for two
things:

* how a user acknowledges a notification;
* which users receive each approved notification.

The decision must remain simple, project-scoped and compatible with the current
Web UI and public API approach. It must not introduce subscriptions, followers,
email routing, desktop push behavior or real-time presence requirements.

---

# Decision

Phase 2 uses a simple per-user in-app notification model.

## Acknowledgment model

Each notification is stored for one recipient user.

Phase 2 supports only two notification states:

* `unread`
* `read`

Acknowledgment is per-user and means marking the notification as `read`.

Phase 2 does **not** support:

* dismiss;
* delete;
* archive;
* snooze;
* notification preferences.

Read notifications remain visible in the user's notification list for the
approved v1 surface. Acknowledgment does not remove them from view.

The Web UI should show a simple empty state when the current user has no
notifications to display.

## Recipient targeting model

Recipients are determined from current Project membership at the time the
notification is generated.

Notifications may only be generated for users who have `read_project` access in
the related Project. No notification is visible outside that Project scope.

The acting user does not receive notifications for their own successful
collaboration actions.

Phase 2 notification targets are:

* `asset locked`: all current Project members except the actor;
* `asset unlocked`: all current Project members except the actor;
* `revision created`: all current Project members except the actor;
* `force unlock`: all current Project members except the actor;
* `conflict detected`: only the acting user whose action was rejected.

If a user loses access to the related Project later, those notifications are no
longer part of their visible notification surface.

Phase 2 does **not** backfill notifications for users who join a Project after
the event occurred.

---

# Consequences

## Positive

* Notification lifecycle stays small and easy to understand.
* Recipient targeting stays aligned with existing tenancy and RBAC boundaries.
* The actor already gets immediate success feedback in the UI without receiving
  redundant self-notifications.

## Trade-offs

* Users cannot manually clear old notifications in Phase 2.
* Project-wide event delivery can be noisier than a future watcher or follower
  model.
* Former members do not receive later visibility into events after losing
  access.

These trade-offs are acceptable because Phase 2 prioritizes a bounded, safe and
fully in-app notification model over more personalized notification behavior.
