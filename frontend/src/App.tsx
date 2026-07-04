import { useEffect, useState } from "react";
import { fetchFoundationStatus, type FoundationStatus } from "./api";
import "./styles.css";

export function App() {
  const [status, setStatus] = useState<FoundationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFoundationStatus()
      .then(setStatus)
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Unknown API error");
      });
  }, []);

  return (
    <main className="app-shell">
      <section className="status-panel" aria-labelledby="openpdm-title">
        <p className="eyebrow">Foundation</p>
        <h1 id="openpdm-title">OpenPDM</h1>
        {status ? (
          <dl className="status-grid">
            <div>
              <dt>Version</dt>
              <dd>{status.version}</dd>
            </div>
            <div>
              <dt>Phase</dt>
              <dd>{status.phase}</dd>
            </div>
            <div>
              <dt>Architecture</dt>
              <dd>{status.architecture}</dd>
            </div>
          </dl>
        ) : (
          <p role={error ? "alert" : "status"}>{error ?? "Connecting to the OpenPDM API..."}</p>
        )}
      </section>
    </main>
  );
}
