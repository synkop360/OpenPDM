import type { ReactNode } from "react";
import { InlineAlert } from "../feedback/InlineAlert";
import { SkipLink } from "../navigation/SkipLink";

type AppShellProps = {
  announcement?: string | null;
  onAnnouncementDismiss?: () => void;
  children: ReactNode;
  header: ReactNode;
  sidebar?: ReactNode;
};

export function AppShell({
  announcement,
  onAnnouncementDismiss,
  children,
  header,
  sidebar,
}: AppShellProps) {
  return (
    <div className={sidebar ? "app-frame" : "app-frame app-frame--no-sidebar"}>
      <SkipLink />
      {sidebar}
      <div className="app-main">
        {header}
        <main className="app-content" id="main-content" tabIndex={-1}>
          {announcement ? (
            <InlineAlert onDismiss={onAnnouncementDismiss} tone="info">
              {announcement}
            </InlineAlert>
          ) : null}
          {children}
        </main>
      </div>
    </div>
  );
}
