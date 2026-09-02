import { Download } from "lucide-react";
import type { Asset, MetadataEntry, Revision } from "../../api";
import type { Loadable } from "../../app/loadable";
import { formatTimestamp } from "../../app/format";

function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

type AssetOverviewProps = {
  asset: Asset;
  metadata: Loadable<MetadataEntry[]>;
  history: Loadable<Revision[]>;
  busyAction: string | null;
  describeActor: (userId: string | null) => string;
  onDownload: (blobId: string, filename: string) => void;
};

/**
 * The Overview tab's curated summary — the "information below the buttons" from
 * the redesign: a key-facts card and a revisions timeline. Relationships live on
 * the Graph tab (reachable from the "Relationship" action button); the full
 * metadata / analysis tooling renders below this on the same tab.
 */
export function AssetOverview({
  asset,
  metadata,
  history,
  busyAction,
  describeActor,
  onDownload,
}: AssetOverviewProps) {
  const metaEntries = metadata.data;
  const revisionsNewestFirst = [...history.data].sort((left, right) => right.number - left.number);
  const latestRevisionNumber = revisionsNewestFirst[0]?.number ?? 0;

  // Asset-level facts only — the plugin-provided metadata keeps its own table
  // below, so nothing here is a duplicate render of a metadata value.
  const facts = [
    { label: "Status", value: asset.status },
    { label: "Revision", value: latestRevisionNumber ? `R${latestRevisionNumber}` : "—" },
    { label: "Source", value: metaEntries[0]?.source ?? "Manual entry" },
    { label: "Owner", value: describeActor(asset.created_by_user_id) },
    { label: "Metadata", value: pluralize(metaEntries.length, "field") },
    { label: "Updated", value: formatTimestamp(asset.updated_at) },
  ].slice(0, 4);

  const revisions = revisionsNewestFirst.slice(0, 5);

  return (
    <div className="asset-overview">
      <article className="detail-card asset-overview__facts">
        {facts.map((fact) => (
          <div className="asset-overview__fact" key={fact.label}>
            <span className="sidebar-section-label">{fact.label}</span>
            <strong>{fact.value}</strong>
          </div>
        ))}
      </article>

      <section className="asset-overview__block">
        <div className="asset-overview__block-header">
          <h3>Revisions</h3>
        </div>
        {revisions.length ? (
          <div className="timeline">
            {revisions.map((revision) => {
              const file = revision.representations.find(
                (representation) => representation.blob_id && representation.blob,
              );
              return (
                <article className="timeline-card" key={revision.id}>
                  <div className="timeline-header">
                    <div>
                      <h3>
                        R{revision.number} — {revision.comment || "No comment"}
                      </h3>
                      <p>
                        {describeActor(revision.created_by_user_id)} ·{" "}
                        {formatTimestamp(revision.created_at)}
                        {file?.blob?.filename ? ` · ${file.blob.filename}` : ""}
                      </p>
                    </div>
                    {file ? (
                      <button
                        className="text-button"
                        disabled={busyAction === `download-${file.blob_id}`}
                        onClick={() =>
                          onDownload(
                            file.blob_id as string,
                            file.blob?.filename ?? `${asset.name}-R${revision.number}.bin`,
                          )
                        }
                        type="button"
                      >
                        <Download aria-hidden="true" /> Download
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="empty-state">No revisions checked in yet.</p>
        )}
      </section>
    </div>
  );
}
