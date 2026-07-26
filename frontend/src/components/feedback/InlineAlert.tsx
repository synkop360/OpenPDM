import type { ReactNode } from "react";

type InlineAlertProps = {
  children: ReactNode;
  title?: string;
  tone?: "info" | "success" | "warning" | "danger";
};

export function InlineAlert({ children, title, tone = "info" }: InlineAlertProps) {
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
    </div>
  );
}
