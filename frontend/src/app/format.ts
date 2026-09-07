import type { NotificationRecord } from "../api";

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
}

/** Compact "just now" / "3m" / "5h" / "2d" / "6w" label for a past ISO timestamp. */
export function formatRelativeTime(value: string, now: number = Date.now()): string {
  const elapsedMs = now - new Date(value).getTime();
  if (!Number.isFinite(elapsedMs) || elapsedMs < 45_000) {
    return "just now";
  }
  const minutes = Math.round(elapsedMs / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d`;
  return `${Math.round(days / 7)}w`;
}

export function formatNotificationEvent(eventType: string): string {
  switch (eventType) {
    case "asset.checked_out":
      return "Asset locked";
    case "asset.unlocked":
      return "Asset unlocked";
    case "asset.force_unlocked":
      return "Force unlock";
    case "revision.created":
      return "Revision created";
    case "collaboration.conflict_detected":
      return "Conflict detected";
    default:
      return eventType;
  }
}

export function notificationSummary(notification: NotificationRecord): string {
  if (notification.event_type === "collaboration.conflict_detected") {
    const guidance = notification.details.user_guidance;
    if (typeof guidance === "string" && guidance.trim()) {
      return guidance;
    }
  }
  const assetId = typeof notification.asset_id === "string" ? notification.asset_id : null;
  if (assetId) {
    return `Related Asset: ${assetId}`;
  }
  return "Project collaboration update.";
}

export function formatRelationshipType(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * Short gloss shown next to a relationship type in a picker, and a fuller
 * directional sentence for a hint line. Both read from the perspective of the
 * Asset the relationship starts at ("this Asset") pointing at the linked Asset.
 */
const RELATIONSHIP_TYPE_COPY: Record<string, { gloss: string; hint: string }> = {
  depends_on: {
    gloss: "needs the linked Asset",
    hint: "This Asset needs the linked Asset to be complete or to function.",
  },
  references: {
    gloss: "points to it for context",
    hint: "This Asset points to the linked Asset for context, without relying on it.",
  },
  derived_from: {
    gloss: "was created from it",
    hint: "This Asset was created from the linked Asset as its source.",
  },
  generates: {
    gloss: "produces it as output",
    hint: "This Asset produces the linked Asset as an output.",
  },
  supersedes: {
    gloss: "replaces an older Asset",
    hint: "This Asset replaces the linked Asset, which is now outdated.",
  },
  related_to: {
    gloss: "general association",
    hint: "This Asset is loosely associated with the linked Asset — use when no other type fits.",
  },
};

/** One-line label for a relationship type option, e.g. "depends on — needs the linked Asset". */
export function formatRelationshipTypeOption(value: string): string {
  const copy = RELATIONSHIP_TYPE_COPY[value];
  return copy ? `${formatRelationshipType(value)} — ${copy.gloss}` : formatRelationshipType(value);
}

/** Directional sentence describing what a relationship type means. */
export function describeRelationshipType(value: string): string {
  return RELATIONSHIP_TYPE_COPY[value]?.hint ?? "";
}
