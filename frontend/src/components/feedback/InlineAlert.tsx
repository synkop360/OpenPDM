import type { ReactNode } from "react";

type InlineAlertProps = {
  children: ReactNode;
  title?: string;
  tone?: "info" | "success" | "warning" | "danger";
  /** When provided, renders a dismiss (×) control that calls this. */
  onDismiss?: () => void;
  dismissLabel?: string;
};

export function InlineAlert({
  children,
  title,
  tone = "info",
  onDismiss,
  dismissLabel = "Dismiss message",
}: InlineAlertProps) {
  return (
    <div
      className={`inline-alert inline-alert--${tone}`}
      role={tone === "danger" ? "alert" : "status"}
    >
      <span className="inline-alert__indicator" aria-hidden="true" />
      <div>
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
      {onDismiss ? (
        <button
          aria-label={dismissLabel}
          className="inline-alert__dismiss"
          onClick={onDismiss}
          type="button"
        >
          <span aria-hidden="true">×</span>
        </button>
      ) : null}
    </div>
  );
}
