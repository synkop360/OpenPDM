import { InlineAlert } from "../../components/feedback/InlineAlert";
import { formatRelationshipType, formatTimestamp } from "../../app/format";
import { describeProvenanceMetadata } from "../../app/provenance";
import type { Loadable } from "../../app/loadable";
import type { AssetGraph, ReferenceRecord, Relationship } from "../../api";
import { AssetGraphDiagram } from "./AssetGraphDiagram";

function ProvenanceNote({ metadata }: { metadata: Record<string, unknown> }) {
  const summary = describeProvenanceMetadata(metadata);
  if (!summary) {
    return null;
  }
  return (
    <>
      <small>{summary}</small>
      <details className="manifest-review">
        <summary>Technical details</summary>
        <dl>
          {Object.entries(metadata).map(([key, value]) => (
            <div key={key}>
              <dt><code>{key}</code></dt>
              <dd><code>{typeof value === "string" ? value : JSON.stringify(value)}</code></dd>
            </div>
          ))}
        </dl>
      </details>
    </>
  );
}

export type RelationshipsGraphSectionProps = {
  assetGraph: Loadable<AssetGraph | null>;
  assetNameById: Map<string, string>;
  assetReferences: Loadable<ReferenceRecord[]>;
  assetRelationships: Loadable<Relationship[]>;
  incomingRelationships: Loadable<Relationship[]>;
  onSelectAsset: (assetId: string) => void;
  outgoingRelationships: Loadable<Relationship[]>;
};

export function RelationshipsGraphSection({
  assetGraph,
  assetNameById,
  assetReferences,
  assetRelationships,
  incomingRelationships,
  onSelectAsset,
  outgoingRelationships,
}: RelationshipsGraphSectionProps) {
  return (
    <>
      <article className="detail-card relationship-card">
        <div className="detail-row">
          <div>
            <h3>Asset relationships</h3>
            <p>
              Explore explicit Asset-to-Asset links without adding engineering-domain
              semantics.
            </p>
          </div>
          <span className="status-pill">
            {assetRelationships.data.length} link
            {assetRelationships.data.length === 1 ? "" : "s"}
          </span>
        </div>

        {assetRelationships.status === "error" ||
        incomingRelationships.status === "error" ||
        outgoingRelationships.status === "error" ? (
          <InlineAlert tone="danger">
            {assetRelationships.error ??
              incomingRelationships.error ??
              outgoingRelationships.error}
          </InlineAlert>
        ) : null}

        <div className="relationship-grid">
          <section className="relationship-column">
            <div className="relationship-column-header">
              <h4>Incoming</h4>
              <span>{incomingRelationships.data.length}</span>
            </div>
            {incomingRelationships.data.length > 0 ? (
              <div className="relationship-list">
                {incomingRelationships.data.map((relationship) => (
                  <article key={relationship.id} className="relationship-item">
                    <div>
                      <strong>{formatRelationshipType(relationship.relationship_type)}</strong>
                      <p>
                        From{" "}
                        {assetNameById.get(relationship.source_asset_id) ??
                          relationship.source_asset_id}
                      </p>
                      <small>{formatTimestamp(relationship.created_at)}</small>
                      <ProvenanceNote metadata={relationship.metadata} />
                    </div>
                    <button
                      className="secondary-button"
                      onClick={() => onSelectAsset(relationship.source_asset_id)}
                      type="button"
                    >
                      Open asset
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">No Assets currently point to this Asset.</p>
            )}
          </section>

          <section className="relationship-column">
            <div className="relationship-column-header">
              <h4>Outgoing</h4>
              <span>{outgoingRelationships.data.length}</span>
            </div>
            {outgoingRelationships.data.length > 0 ? (
              <div className="relationship-list">
                {outgoingRelationships.data.map((relationship) => (
                  <article key={relationship.id} className="relationship-item">
                    <div>
                      <strong>{formatRelationshipType(relationship.relationship_type)}</strong>
                      <p>
                        To{" "}
                        {assetNameById.get(relationship.target_asset_id) ??
                          relationship.target_asset_id}
                      </p>
                      <small>{formatTimestamp(relationship.created_at)}</small>
                      <ProvenanceNote metadata={relationship.metadata} />
                    </div>
                    <button
                      className="secondary-button"
                      onClick={() => onSelectAsset(relationship.target_asset_id)}
                      type="button"
                    >
                      Open asset
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">This Asset has no outgoing relationships yet.</p>
            )}
          </section>
        </div>
      </article>

      <article className="detail-card relationship-card">
        <div className="detail-row">
          <div>
            <h3>Generic references</h3>
            <p>
              References stay distinct from graph edges so unresolved or external pointers
              do not appear as Assets.
            </p>
          </div>
          <span className="status-pill">
            {assetReferences.data.length} reference
            {assetReferences.data.length === 1 ? "" : "s"}
          </span>
        </div>

        {assetReferences.status === "error" ? (
          <InlineAlert tone="danger">{assetReferences.error}</InlineAlert>
        ) : null}

        {assetReferences.data.length > 0 ? (
          <div className="reference-list">
            {assetReferences.data.map((reference) => (
              <article key={reference.id} className="relationship-item reference-item">
                <div>
                  <strong>{reference.label || reference.reference_type}</strong>
                  <p>{reference.target_uri}</p>
                  <small>{reference.reference_type}</small>
                  <ProvenanceNote metadata={reference.metadata} />
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">
            No generic references are attached to this Asset yet.
          </p>
        )}
      </article>

      <article className="detail-card relationship-card">
        <div className="detail-row">
          <div>
            <h3>Bounded graph summary</h3>
            <p>
              The Web UI uses the approved Phase 3 bounded graph read with direction{" "}
              <code>both</code> and depth <code>3</code>.
            </p>
          </div>
          <span className="status-pill">
            {assetGraph.data?.has_cycle ? "cycle detected" : "no cycle"}
          </span>
        </div>

        {assetGraph.status === "error" ? (
          <InlineAlert tone="danger">{assetGraph.error}</InlineAlert>
        ) : null}

        {assetGraph.data ? (
          assetGraph.data.nodes.length > 0 ? (
            <>
              <AssetGraphDiagram graph={assetGraph.data} onSelectAsset={onSelectAsset} />
              <p className="muted-text graph-diagram-caption">
                {assetGraph.data.nodes.length} node{assetGraph.data.nodes.length === 1 ? "" : "s"},{" "}
                {assetGraph.data.relationships.length} relationship
                {assetGraph.data.relationships.length === 1 ? "" : "s"}, direction{" "}
                {assetGraph.data.direction}, max depth {assetGraph.data.max_depth}.
                {assetGraph.data.target_asset_id
                  ? ` Path to ${assetGraph.data.target_asset_id} ${assetGraph.data.path_exists ? "exists" : "does not exist"}.`
                  : ""}
              </p>
            </>
          ) : (
            <p className="empty-state">No related Assets within the bounded traversal depth.</p>
          )
        ) : (
          <p className="empty-state">Graph summary is loading for this Asset.</p>
        )}
      </article>
    </>
  );
}
