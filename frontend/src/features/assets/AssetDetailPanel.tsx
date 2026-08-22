import { useState } from "react";
import { X } from "lucide-react";
import { InlineAlert } from "../../components/feedback/InlineAlert";
import { formatNotificationEvent, formatTimestamp, notificationSummary } from "../../app/format";
import type { Loadable } from "../../app/loadable";
import type { Asset, NotificationRecord } from "../../api";
import { AssetDetailTabs, type AssetDetailTab } from "./AssetDetailTabs";
import { MetadataAnalysisSection, type MetadataAnalysisSectionProps } from "./MetadataAnalysisSection";
import { RelationshipsGraphSection, type RelationshipsGraphSectionProps } from "./RelationshipsGraphSection";
import { HistoryCollaborationSection, type HistoryCollaborationSectionProps } from "./HistoryCollaborationSection";

type AssetDetailPanelProps = MetadataAnalysisSectionProps &
  RelationshipsGraphSectionProps &
  HistoryCollaborationSectionProps & {
    assetDetail: Loadable<Asset | null>;
    notifications: Loadable<NotificationRecord[]>;
    onClose: () => void;
    onMarkNotificationRead: (notificationId: string) => void;
    onRefreshNotifications: () => void;
    selectedAssetId: string | null;
    unreadNotifications: number;
  };

export function AssetDetailPanel({
  assetDetail,
  busyAction,
  notifications,
  onClose,
  onMarkNotificationRead,
  onRefreshNotifications,
  selectedAssetId,
  unreadNotifications,
  ...sectionProps
}: AssetDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<AssetDetailTab>("metadata");

  return (
    <section className={selectedAssetId ? "panel detail-panel asset-detail-sheet is-open" : "panel detail-panel asset-detail-sheet"}>
      <header className="panel-header panel-header-compact">
        <button aria-label="Close Asset detail" className="icon-button close-detail-button" onClick={onClose} type="button"><X /></button>
      </header>

      <article className="detail-card notification-card">
        <div className="detail-row">
          <div>
            <h3>Collaboration notifications</h3>
            <p>
              {unreadNotifications > 0
                ? `${unreadNotifications} unread notification${unreadNotifications === 1 ? "" : "s"}`
                : "No unread notifications"}
            </p>
          </div>
          <button
            className="secondary-button"
            disabled={busyAction === "refresh-notifications"}
            onClick={onRefreshNotifications}
            type="button"
          >
            {busyAction === "refresh-notifications" ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {notifications.status === "error" ? (
          <InlineAlert tone="danger">{notifications.error}</InlineAlert>
        ) : null}

        {notifications.data.length > 0 ? (
          <div className="timeline">
            {notifications.data.map((notification) => (
              <article key={notification.id} className="timeline-card notification-item">
                <div className="timeline-header">
                  <div>
                    <h3>{formatNotificationEvent(notification.event_type)}</h3>
                    <p>{notificationSummary(notification)}</p>
                  </div>
                  <small>{formatTimestamp(notification.created_at)}</small>
                </div>
                <div className="notification-meta">
                  <span
                    className={
                      notification.is_read
                        ? "status-pill notification-pill notification-read"
                        : "status-pill notification-pill notification-unread"
                    }
                  >
                    {notification.is_read ? "read" : "unread"}
                  </span>
                  {!notification.is_read ? (
                    <button
                      className="secondary-button"
                      disabled={busyAction === `read-notification-${notification.id}`}
                      onClick={() => onMarkNotificationRead(notification.id)}
                      type="button"
                    >
                      {busyAction === `read-notification-${notification.id}`
                        ? "Marking..."
                        : "Mark as read"}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">
            Collaboration notifications will appear here when approved Phase 2 events target
            your account.
          </p>
        )}
      </article>

      {selectedAssetId && assetDetail.data ? (
        <>
          <article className="detail-card asset-summary-card">
            <div className="detail-row">
              <div>
                <h3>{assetDetail.data.name}</h3>
                <p>{assetDetail.data.description || "No description."}</p>
              </div>
              <span className="status-pill">{assetDetail.data.status}</span>
            </div>
            <p className="muted-text">
              Created {formatTimestamp(assetDetail.data.created_at)} and updated{" "}
              {formatTimestamp(assetDetail.data.updated_at)}.
            </p>
          </article>

          <AssetDetailTabs onValueChange={setActiveTab} value={activeTab} />

          {activeTab === "metadata" ? (
            <MetadataAnalysisSection busyAction={busyAction} {...sectionProps} />
          ) : null}
          {activeTab === "relationships" ? <RelationshipsGraphSection {...sectionProps} /> : null}
          {activeTab === "history" ? (
            <HistoryCollaborationSection busyAction={busyAction} {...sectionProps} />
          ) : null}
        </>
      ) : (
        <p className="empty-state">
          Select an Engineering Asset to inspect immutable Revision history and Blob-backed
          Representations.
        </p>
      )}
    </section>
  );
}
