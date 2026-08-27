import { InlineAlert } from "../../components/feedback/InlineAlert";
import {
  collaborationGuidance,
  collaborationRecoveryAction,
  collaborationRequestId,
  collaborationShouldRefresh,
} from "../../app/collaborationErrors";
import { formatTimestamp } from "../../app/format";
import type { Loadable } from "../../app/loadable";
import type { ApiError, CollaborationState, Revision, TimelineEntry } from "../../api";

export type HistoryCollaborationSectionProps = {
  assetHistory: Loadable<Revision[]>;
  assetTimeline: Loadable<TimelineEntry[]>;
  busyAction: string | null;
  collaborationError: ApiError | null;
  collaborationState: Loadable<CollaborationState | null>;
  currentUserId: string | undefined;
  describeActor: (userId: string | null) => string;
  onCheckout: () => void;
  onDownload: (blobId: string, filename: string) => void;
  onRefreshAssetState: () => void;
  onUnlock: (force: boolean) => void;
};

export function HistoryCollaborationSection({
  assetHistory,
  assetTimeline,
  busyAction,
  collaborationError,
  collaborationState,
  currentUserId,
  describeActor,
  onCheckout,
  onDownload,
  onRefreshAssetState,
  onUnlock,
}: HistoryCollaborationSectionProps) {
  return (
    <>
      <article className="detail-card collaboration-card">
        <div className="detail-row">
          <div>
            <h3>Collaboration state</h3>
            <p>
              {collaborationState.data
                ? `State: ${collaborationState.data.state}`
                : "Loading collaboration state..."}
            </p>
          </div>
          <span
            className={`status-pill collaboration-pill collaboration-${collaborationState.data?.state ?? "unknown"}`}
          >
            {collaborationState.data?.state ?? "loading"}
          </span>
        </div>
        {collaborationState.data?.lock ? (
          <p className="muted-text">
            Lock owner:{" "}
            {collaborationState.data.lock.owner_user_id === currentUserId
              ? "You"
              : collaborationState.data.lock.owner_user_id}
          </p>
        ) : (
          <p className="muted-text">No active collaboration lock.</p>
        )}
        <div className="collaboration-actions">
          <button
            className="secondary-button warning-button"
            disabled={busyAction === "force-unlock" || !collaborationState.data?.can_force_unlock}
            onClick={() => onUnlock(true)}
            type="button"
          >
            {busyAction === "force-unlock" ? "Force-unlocking..." : "Force unlock"}
          </button>
        </div>
      </article>

      {collaborationState.status === "error" ? (
        <InlineAlert tone="danger">{collaborationState.error}</InlineAlert>
      ) : null}

      {collaborationError ? (
        <article className="detail-card recovery-card">
          <h3>Recovery guidance</h3>
          <p>{collaborationGuidance(collaborationError)}</p>
          {collaborationRequestId(collaborationError) ? (
            <p className="muted-text">
              Request ID: {collaborationRequestId(collaborationError)}
            </p>
          ) : null}
          <div className="collaboration-actions">
            {collaborationShouldRefresh(collaborationError) ? (
              <button
                className="secondary-button"
                disabled={busyAction === "refresh-state"}
                onClick={() => onRefreshAssetState()}
                type="button"
              >
                {busyAction === "refresh-state" ? "Refreshing..." : "Refresh asset state"}
              </button>
            ) : null}
            {collaborationRecoveryAction(collaborationError) === "checkout_asset" ? (
              <button
                className="secondary-button"
                disabled={
                  busyAction === "checkout" || collaborationState.data?.state === "locked"
                }
                onClick={() => onCheckout()}
                type="button"
              >
                Check out now
              </button>
            ) : null}
          </div>
        </article>
      ) : null}

      {assetTimeline.status === "error" ? (
        <InlineAlert tone="danger">{assetTimeline.error}</InlineAlert>
      ) : null}

      <div className="timeline">
        <h3>Collaboration timeline</h3>
        {assetTimeline.data.map((entry) => (
          <article
            key={`${entry.event_type}-${entry.occurred_at}-${entry.revision_id ?? "none"}`}
            className="timeline-card"
          >
            <div className="timeline-header">
              <div>
                <h3>{entry.event_type}</h3>
                <p>
                  {describeActor(entry.actor_user_id)}
                </p>
              </div>
              <small>{formatTimestamp(entry.occurred_at)}</small>
            </div>
            {entry.revision_id ? (
              <p className="muted-text">Revision: {entry.revision_id}</p>
            ) : null}
          </article>
        ))}
      </div>

      {assetHistory.status === "error" ? (
        <InlineAlert tone="danger">{assetHistory.error}</InlineAlert>
      ) : null}

      <div className="timeline">
        <h3>Revision comments and history</h3>
        {assetHistory.data.map((revision) => (
          <article key={revision.id} className="timeline-card">
            <div className="timeline-header">
              <div>
                <h3>Revision {revision.number}</h3>
                <p>{revision.comment || "No revision comment."}</p>
              </div>
              <small>{formatTimestamp(revision.created_at)}</small>
            </div>
            {revision.representations.length > 0 ? (
              <ul className="representation-list">
                {revision.representations.map((representation) => (
                  <li key={representation.id}>
                    <div>
                      <strong>{representation.name}</strong>
                      <span>{representation.media_type}</span>
                      <small>{representation.blob?.filename ?? "No Blob attached"}</small>
                    </div>
                    {representation.blob_id && representation.blob ? (
                      <button
                        className="secondary-button"
                        disabled={busyAction === `download-${representation.blob_id}`}
                        onClick={() =>
                          onDownload(
                            representation.blob_id!,
                            representation.blob?.filename ?? `${representation.name}.bin`,
                          )
                        }
                        type="button"
                      >
                        {busyAction === `download-${representation.blob_id}`
                          ? "Preparing..."
                          : "Download"}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-text">No Representations for this Revision yet.</p>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
