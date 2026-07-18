import type { FoundationStatus } from "../../api";
import type { Loadable } from "../../app/loadable";

type GuestHeaderProps = {
  foundation: Loadable<FoundationStatus | null>;
};

export function GuestHeader({ foundation }: GuestHeaderProps) {
  return (
    <section className="hero-panel auth-hero">
      <div>
        <p className="eyebrow">Engineering Collaboration Platform</p>
        <h1>OpenPDM</h1>
        <p className="intro">Organize, version, relate and secure Engineering Assets through one open platform.</p>
      </div>
      <dl className="foundation-grid">
        <div><dt>API Status</dt><dd>{foundation.data ? foundation.data.phase : foundation.error ?? "Loading..."}</dd></div>
        <div><dt>Architecture</dt><dd>{foundation.data?.architecture ?? "Connecting..."}</dd></div>
        <div><dt>Version</dt><dd>{foundation.data?.version ?? "Unknown"}</dd></div>
      </dl>
    </section>
  );
}
