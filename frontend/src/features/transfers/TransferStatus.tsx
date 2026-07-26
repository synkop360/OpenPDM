export type TransferPhase =
  | "idle" | "preparing" | "uploading" | "verifying" | "checking-in"
  | "failed" | "cancelled" | "awaiting-file" | "success" | "permission";

const labels: Record<Exclude<TransferPhase, "idle">, string> = {
  preparing: "Preparing transfer",
  uploading: "Uploading file",
  verifying: "Verifying file integrity",
  "checking-in": "Creating immutable Revision",
  failed: "Transfer interrupted",
  cancelled: "Transfer cancelled",
  "awaiting-file": "Resume transfer",
  success: "Check-in complete",
  permission: "Check-in unavailable",
};

export function TransferStatus({ phase, receivedBytes, totalBytes, message, onCancel, onRetry, onDiscard,
  retryLabel = "Retry check-in" }: {
  phase: TransferPhase;
  receivedBytes: number;
  totalBytes: number;
  message?: string | null;
  onCancel?: () => void;
  onRetry?: () => void;
  onDiscard?: () => void;
  retryLabel?: string;
}) {
  if (phase === "idle") return null;
  const active = phase === "preparing" || phase === "uploading" || phase === "verifying";
  return (
    <section className={`transfer-status transfer-status-${phase}`} aria-label="Check-in transfer">
      <div role="status" aria-live="polite" aria-atomic="true">
        <strong>{labels[phase]}</strong>
        {message ? <span>{message}</span> : null}
      </div>
      {totalBytes > 0 && (active || phase === "failed") ? (
        <progress aria-label="File upload progress" aria-valuemin={0} aria-valuemax={totalBytes}
          aria-valuenow={receivedBytes} max={totalBytes} value={receivedBytes}>
          {Math.round((receivedBytes / totalBytes) * 100)}%
        </progress>
      ) : null}
      <div className="collaboration-actions">
        {active && onCancel ? <button className="secondary-button" type="button" onClick={onCancel}>Cancel transfer</button> : null}
        {phase === "failed" && onRetry ? <button className="secondary-button" type="button" onClick={onRetry}>{retryLabel}</button> : null}
        {(phase === "failed" || phase === "awaiting-file") && onDiscard ? (
          <button className="secondary-button warning-button" type="button" onClick={onDiscard}>Discard transfer</button>
        ) : null}
      </div>
    </section>
  );
}
