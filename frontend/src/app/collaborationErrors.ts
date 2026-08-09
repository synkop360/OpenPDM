import type { ApiError } from "../api";

export function collaborationGuidance(error: ApiError): string {
  const contextualGuidance = error.context?.user_guidance;
  if (typeof contextualGuidance === "string" && contextualGuidance.trim()) {
    return contextualGuidance;
  }
  switch (error.code) {
    case "asset_locked":
      return "This Asset is already locked by another user. Wait for release or ask a Maintainer to coordinate.";
    case "checkin_without_lock":
      return "Check out the Asset before checking in changes.";
    case "checkin_by_non_owner":
      return "Only the current lock owner can check in changes for this Asset.";
    case "unlock_not_allowed":
      return "Only the lock owner can unlock this Asset unless a Maintainer or Owner force-unlocks.";
    case "asset_archived":
      return "Archived Assets cannot be changed through the collaboration flow.";
    case "no_active_lock":
      return "This Asset no longer has an active collaboration lock. Refresh the state and try again if needed.";
    default:
      return error.message;
  }
}

export function collaborationRecoveryAction(error: ApiError): string | null {
  const value = error.context?.recovery_action;
  return typeof value === "string" ? value : null;
}

export function collaborationRequestId(error: ApiError): string | null {
  const value = error.context?.request_id;
  return typeof value === "string" ? value : null;
}

export function collaborationShouldRefresh(error: ApiError): boolean {
  return error.context?.should_refresh === true;
}
