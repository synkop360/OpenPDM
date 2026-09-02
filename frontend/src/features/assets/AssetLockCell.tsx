import { Lock, LockOpen } from "lucide-react";
import type { Asset } from "../../api";
import { formatRelativeTime } from "../../app/format";

type AssetLockCellProps = {
  asset: Asset;
  currentUserId: string | undefined;
  /** A collaboration mutation is in flight anywhere; disables every row action. */
  busy: boolean;
  onCheckOut: (assetId: string) => void;
  onOpenCheckIn: (assetId: string) => void;
  onTakeOver: (assetId: string) => void;
};

function initials(name: string | null): string {
  if (!name) return "??";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "??";
}

const SMALL_BUTTON = "asset-lock-cell__action";

export function AssetLockCell({
  asset,
  currentUserId,
  busy,
  onCheckOut,
  onOpenCheckIn,
  onTakeOver,
}: AssetLockCellProps) {
  const lock = asset.lock;

  // The list endpoint may predate this field on a stale cache; treat missing as available.
  if (!lock || lock.state === "available") {
    return (
      <div className="asset-lock-cell">
        <span className="asset-lock-cell__status">Available</span>
        <button
          aria-label="Check out this asset"
          className={`secondary-button ${SMALL_BUTTON}`}
          disabled={busy}
          onClick={() => onCheckOut(asset.id)}
          type="button"
        >
          Check out
        </button>
      </div>
    );
  }

  const mine = lock.is_mine || (currentUserId != null && lock.owner_user_id === currentUserId);
  const age = lock.locked_at ? formatRelativeTime(lock.locked_at) : null;

  if (lock.state === "stale_lock") {
    return (
      <div className="asset-lock-cell is-stale">
        <span className="asset-lock-cell__who">
          <span className="asset-lock-cell__avatar" aria-hidden="true">
            {initials(lock.owner_display_name)}
          </span>
          <span>Stale{age ? ` · ${age}` : ""}</span>
        </span>
        {lock.can_take_over ? (
          <button
            aria-label="Take over this stale lock"
            className={`warning-button secondary-button ${SMALL_BUTTON}`}
            disabled={busy}
            onClick={() => onTakeOver(asset.id)}
            type="button"
          >
            <LockOpen aria-hidden="true" /> Take over
          </button>
        ) : (
          <span className="asset-lock-cell__note">Owner cannot write here</span>
        )}
      </div>
    );
  }

  // state === "locked"
  return (
    <div className={mine ? "asset-lock-cell is-mine" : "asset-lock-cell"}>
      <span className="asset-lock-cell__who">
        <span className="asset-lock-cell__avatar" aria-hidden="true">
          {mine ? "You" : initials(lock.owner_display_name)}
        </span>
        <span>
          {mine ? "You" : lock.owner_display_name ?? "Another user"}
          {age ? ` · ${age}` : ""}
        </span>
      </span>
      {mine ? (
        <button
          aria-label="Check in this asset"
          className={`primary-button ${SMALL_BUTTON}`}
          disabled={busy}
          onClick={() => onOpenCheckIn(asset.id)}
          type="button"
        >
          Check in
        </button>
      ) : (
        <button
          aria-label={`Locked by ${lock.owner_display_name ?? "another user"}`}
          className={`secondary-button ${SMALL_BUTTON}`}
          disabled
          type="button"
        >
          <Lock aria-hidden="true" /> Locked
        </button>
      )}
    </div>
  );
}
