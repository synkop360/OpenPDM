import type { ReactNode } from "react";
import { InlineAlert } from "../feedback/InlineAlert";
import { SkipLink } from "../navigation/SkipLink";

type AppShellProps = {
  announcement?: string | null;
  children: ReactNode;
  header: ReactNode;
};

export function AppShell({ announcement, children, header }: AppShellProps) {
  return (
    <>
      <SkipLink />
      <main className="app-shell" id="main-content" tabIndex={-1}>
        {header}
        {announcement ? <InlineAlert tone="info">{announcement}</InlineAlert> : null}
        {children}
      </main>
    </>
  );
}
