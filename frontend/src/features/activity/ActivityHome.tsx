import { Bell, Inbox, Lock, RefreshCw } from "lucide-react";
import type { ActorLock, NotificationRecord } from "../../api";
import type { Loadable } from "../../app/loadable";
import { formatNotificationEvent, formatRelativeTime, notificationSummary } from "../../app/format";
import { InlineAlert } from "../../components/feedback/InlineAlert";

type ActivityHomeProps = {
  displayName: string;
  checkouts: Loadable<ActorLock[]>;
  notifications: NotificationRecord[];
  notificationsBusy: boolean;
  notificationsError: string | null;
  onOpenAsset: (projectId: string, assetId: string) => void;
  onOpenProjectAssets: (projectId: string) => void;
  onRefresh: () => void;
};

export function ActivityHome({
  displayName,
  checkouts,
  notifications,
  notificationsBusy,
  notificationsError,
  onOpenAsset,
  onOpenProjectAssets,
  onRefresh,
}: ActivityHomeProps) {
  const held = checkouts.data;
  const stale = held.filter((lock) => lock.state === "stale_lock");
  const unread = notifications.filter((item) => !item.is_read);

  // De-duped list of the projects the user has an open checkout in — the
  // "jump back in" shortcuts.
  const recentProjects = Array.from(
    new Map(held.map((lock) => [lock.project_id, lock.project_name])).entries(),
  );

  return (
    <div className="activity-home">
      <div className="activity-home__main">
        <section className="panel activity-attention">
          <header className="panel-header" style={{ marginBottom: 8 }}>
            <div>
              <p className="eyebrow">Waiting on you</p>
              <h2>
                {stale.length
                  ? `${stale.length} lock${stale.length === 1 ? "" : "s"} need${stale.length === 1 ? "s" : ""} a decision`
                  : held.length
                    ? `You are holding ${held.length} checkout${held.length === 1 ? "" : "s"}`
                    : "Nothing needs your attention"}
              </h2>
            </div>
            <span className="status-pill">
              {held.length} lock{held.length === 1 ? "" : "s"} · {unread.length} unread
            </span>
          </header>

          {checkouts.status === "error" ? (
            <InlineAlert tone="danger">{checkouts.error}</InlineAlert>
          ) : null}

          <div className="timeline">
            {stale.map((lock) => (
              <article
                className="timeline-card activity-attention__card is-warning"
                key={lock.asset_id}
              >
                <div className="timeline-header">
                  <div>
                    <h3>{lock.asset_name} — your lock went stale</h3>
                    <p>
                      {lock.project_name} · locked {formatRelativeTime(lock.locked_at)} ago
                    </p>
                  </div>
                  <button
                    className="secondary-button"
                    onClick={() => onOpenAsset(lock.project_id, lock.asset_id)}
                    type="button"
                  >
                    Review
                  </button>
                </div>
              </article>
            ))}
            {held
              .filter((lock) => lock.state !== "stale_lock")
              .map((lock) => (
                <article className="timeline-card" key={lock.asset_id}>
                  <div className="timeline-header">
                    <div>
                      <h3>{lock.asset_name} is checked out to you</h3>
                      <p>
                        {lock.project_name} · {formatRelativeTime(lock.locked_at)} ago
                      </p>
                    </div>
                    <button
                      className="secondary-button"
                      onClick={() => onOpenAsset(lock.project_id, lock.asset_id)}
                      type="button"
                    >
                      Open
                    </button>
                  </div>
                </article>
              ))}
            {!held.length && checkouts.status !== "loading" ? (
              <div className="empty-state operational-empty">
                <Lock aria-hidden="true" />
                <h3>No open checkouts</h3>
                <p>Check an Asset out from a project workspace to start working on it.</p>
              </div>
            ) : null}
          </div>
        </section>

        <section className="panel activity-feed">
          <header className="panel-header" style={{ marginBottom: 8 }}>
            <div>
              <p className="eyebrow">Feed</p>
              <h2>Recent activity</h2>
            </div>
            <button
              className="secondary-button"
              disabled={notificationsBusy}
              onClick={onRefresh}
              type="button"
            >
              <RefreshCw aria-hidden="true" /> Refresh
            </button>
          </header>

          {notificationsError ? <InlineAlert tone="danger">{notificationsError}</InlineAlert> : null}

          {notifications.length ? (
            <div className="compact-list">
              {notifications.slice(0, 12).map((notification) => (
                <button
                  className="activity-feed__row"
                  key={notification.id}
                  onClick={() =>
                    notification.asset_id
                      ? onOpenAsset(notification.project_id, notification.asset_id)
                      : onOpenProjectAssets(notification.project_id)
                  }
                  type="button"
                >
                  <span className="activity-feed__text">
                    <strong>{formatNotificationEvent(notification.event_type)}</strong>
                    <small>{notificationSummary(notification)}</small>
                  </span>
                  <small className="mono activity-feed__time">
                    {formatRelativeTime(notification.created_at)}
                  </small>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state operational-empty">
              <Bell aria-hidden="true" />
              <h3>No activity yet</h3>
              <p>Collaboration events across your projects will show up here.</p>
            </div>
          )}
        </section>
      </div>

      <aside className="activity-home__rail">
        <section className="panel">
          <h3 style={{ margin: 0 }}>Your checkouts</h3>
          <div className="compact-list" style={{ marginTop: 12 }}>
            {held.length ? (
              held.map((lock) => (
                <button
                  className="activity-feed__row"
                  key={lock.asset_id}
                  onClick={() => onOpenAsset(lock.project_id, lock.asset_id)}
                  type="button"
                >
                  <span className="activity-feed__text">
                    <strong>{lock.asset_name}</strong>
                    <small>{lock.project_name}</small>
                  </span>
                  <small className="mono activity-feed__time">
                    {formatRelativeTime(lock.locked_at)}
                  </small>
                </button>
              ))
            ) : (
              <p className="muted-text" style={{ margin: 0, fontSize: "0.8rem" }}>
                Nothing checked out.
              </p>
            )}
          </div>
        </section>

        {recentProjects.length ? (
          <section className="panel">
            <h3 style={{ margin: 0 }}>Jump back in</h3>
            <div className="compact-list" style={{ marginTop: 12 }}>
              {recentProjects.map(([projectId, projectName]) => (
                <button
                  className="secondary-button"
                  key={projectId}
                  onClick={() => onOpenProjectAssets(projectId)}
                  style={{ justifyContent: "flex-start" }}
                  type="button"
                >
                  <Inbox aria-hidden="true" /> {projectName}
                </button>
              ))}
            </div>
          </section>
        ) : null}

        <p className="muted-text" style={{ fontSize: "0.75rem", margin: 0 }}>
          Signed in as {displayName}.
        </p>
      </aside>
    </div>
  );
}
