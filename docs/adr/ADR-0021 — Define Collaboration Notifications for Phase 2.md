# ADR-0021 — Define Collaboration Notifications for Phase 2

**Status:** Accepted

---

# Context

Phase 2 needs user-visible collaboration feedback, but it must avoid premature expansion into multi-channel delivery infrastructure.

Notification behavior must stay aligned with the approved v1 scope and avoid introducing desktop-specific or external integration behavior.

---

# Decision

Phase 2 supports **in-app notifications only**.

The approved notification-triggering events are:

* `asset locked`
* `asset unlocked`
* `revision created`
* `force unlock`
* `conflict detected`

Phase 2 explicitly does **not** include:

* email notifications;
* webhooks;
* desktop push notifications;
* Slack or Teams notifications.

---

# Consequences

## Positive

* Notification scope remains simple and achievable for v1.
* Collaboration feedback stays within the supported product surface.
* Later notification channels remain possible without changing the Phase 2 model.

## Trade-offs

* Users do not receive out-of-app collaboration alerts in Phase 2.
* Later delivery channels will require additional design and implementation work.

These trade-offs are acceptable because OpenPDM currently prioritizes clear in-app collaboration feedback over broader notification infrastructure.

