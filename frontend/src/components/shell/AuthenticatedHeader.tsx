import { Bell, ChevronRight, LogOut, Menu } from "lucide-react";
import type { LoadableStatus } from "../../app/loadable";

export type BreadcrumbItem = {
  key: string;
  label: string;
  onClick?: () => void;
};

type AuthenticatedHeaderProps = {
  apiError: string | null;
  apiLabel: string;
  apiStatus: LoadableStatus;
  breadcrumb: BreadcrumbItem[];
  displayName: string;
  email: string;
  onNotifications: () => void;
  onOpenNavigation: () => void;
  onSignOut: () => void;
  unreadNotifications: number;
};

export function AuthenticatedHeader({
  apiError,
  apiLabel,
  apiStatus,
  breadcrumb,
  displayName,
  email,
  onNotifications,
  onOpenNavigation,
  onSignOut,
  unreadNotifications,
}: AuthenticatedHeaderProps) {
  return (
    <header className="app-topbar">
      <button
        aria-label="Open navigation"
        className="icon-button mobile-menu-button"
        onClick={onOpenNavigation}
        type="button"
      >
        <Menu />
      </button>
      <nav aria-label="Breadcrumb" className="topbar-breadcrumb">
        {breadcrumb.map((item, index) => (
          <span className="topbar-breadcrumb-segment" key={item.key}>
            {index > 0 ? <ChevronRight aria-hidden="true" className="ic14" /> : null}
            {item.onClick ? (
              <button onClick={item.onClick} type="button">{item.label}</button>
            ) : (
              <strong>{item.label}</strong>
            )}
          </span>
        ))}
      </nav>
      <div className="topbar-actions">
        <div className="topbar-status" data-status={apiStatus} title={apiError ?? undefined}>
          <span className="health-dot" />
          {apiStatus === "error" ? "API unavailable" : apiLabel}
        </div>
        <button className="icon-button" aria-label="Notifications" onClick={onNotifications} type="button">
          <Bell />
          {unreadNotifications ? <span className="notification-count">{unreadNotifications}</span> : null}
        </button>
        <div className="topbar-divider" />
        <div className="user-identity" title={email}>
          <div className="user-avatar">{displayName.slice(0, 2).toUpperCase()}</div>
          <span className="user-identity-text">
            <strong>{displayName}</strong>
            <small>{email}</small>
          </span>
        </div>
        <button className="icon-button" aria-label="Sign out" onClick={onSignOut} type="button">
          <LogOut />
        </button>
      </div>
    </header>
  );
}
