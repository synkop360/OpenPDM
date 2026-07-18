import { Bell, Boxes, LogOut, Menu } from "lucide-react";
import type { LoadableStatus } from "../../app/loadable";

type AuthenticatedHeaderProps = {
  apiError: string | null;
  apiLabel: string;
  apiStatus: LoadableStatus;
  displayName: string;
  email: string;
  onHome: () => void;
  onNotifications: () => void;
  onOpenNavigation: () => void;
  onSignOut: () => void;
  unreadNotifications: number;
};

export function AuthenticatedHeader({
  apiError,
  apiLabel,
  apiStatus,
  displayName,
  email,
  onHome,
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
      <button className="brand" onClick={onHome} type="button">
        <span className="brand-mark"><Boxes /></span>
        <span><strong>OpenPDM</strong><small>Engineering collaboration</small></span>
      </button>
      <div className="topbar-status" data-status={apiStatus} title={apiError ?? undefined}>
        <span className="health-dot" />
        {apiStatus === "error" ? "API unavailable" : apiLabel}
      </div>
      <button className="icon-button" aria-label="Notifications" onClick={onNotifications} type="button">
        <Bell />
        {unreadNotifications ? <span className="notification-count">{unreadNotifications}</span> : null}
      </button>
      <div className="user-avatar" title={email}>
        {displayName.slice(0, 2).toUpperCase()}
      </div>
      <button className="icon-button" aria-label="Sign out" onClick={onSignOut} type="button">
        <LogOut />
      </button>
    </header>
  );
}
