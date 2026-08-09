import type { NotificationRecord } from "../api";

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString();
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

export function formatMetadataSummary(metadata: Record<string, unknown>): string | null {
  const entries = Object.entries(metadata);
  if (entries.length === 0) {
    return null;
  }
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" • ");
}
