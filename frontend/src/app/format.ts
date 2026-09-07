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
