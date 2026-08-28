import type { FormEvent } from "react";
import { InlineAlert } from "../../components/feedback/InlineAlert";
import { formatRelationshipType, formatTimestamp } from "../../app/format";
import { describeProvenanceMetadata } from "../../app/provenance";
import type { Loadable } from "../../app/loadable";
import { RELATIONSHIP_TYPES, type Asset, type AssetGraph, type Relationship, type RelationshipType } from "../../api";
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
  assetRelationships: Loadable<Relationship[]>;
  assets: Asset[];
  busyAction: string | null;
  incomingRelationships: Loadable<Relationship[]>;
  onCreateRelationship: (event: FormEvent<HTMLFormElement>) => void;
  onRelationshipTargetChange: (value: string) => void;
  onRelationshipTypeChange: (value: RelationshipType) => void;
  onSelectAsset: (assetId: string) => void;
  outgoingRelationships: Loadable<Relationship[]>;
  relationshipForm: { targetAssetId: string; relationshipType: RelationshipType };
  relationshipFormError: string | null;
  selectedAssetId: string | null;
};

export function RelationshipsGraphSection({
  assetGraph,
  assetNameById,
  assetRelationships,
  assets,
  busyAction,
  incomingRelationships,
  onCreateRelationship,
  onRelationshipTargetChange,
  onRelationshipTypeChange,
  onSelectAsset,
  outgoingRelationships,
  relationshipForm,
  relationshipFormError,
  selectedAssetId,
}: RelationshipsGraphSectionProps) {
  const candidateTargets = assets
    .filter((asset) => asset.id !== selectedAssetId)
    .sort((a, b) => a.name.localeCompare(b.name));

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

        <form className="form-grid compact-form relationship-create-form" onSubmit={onCreateRelationship}>
          <h4>Link to another Asset</h4>
          <label>
            Target Asset
            <select
              disabled={candidateTargets.length === 0}
              onChange={(event) => onRelationshipTargetChange(event.target.value)}
              required
              value={relationshipForm.targetAssetId}
            >
              <option value="">Select an Asset</option>
              {candidateTargets.map((asset) => (
                <option key={asset.id} value={asset.id}>{asset.name}</option>
              ))}
            </select>
          </label>
          <label>
            Relationship type
            <select
              onChange={(event) => onRelationshipTypeChange(event.target.value as RelationshipType)}
              value={relationshipForm.relationshipType}
            >
              {RELATIONSHIP_TYPES.map((type) => (
                <option key={type} value={type}>{formatRelationshipType(type)}</option>
              ))}
            </select>
          </label>
          {relationshipFormError ? <InlineAlert tone="danger">{relationshipFormError}</InlineAlert> : null}
          {candidateTargets.length === 0 ? (
            <p className="muted-text">
              No other Assets are loaded in this Project to link to yet.
            </p>
          ) : null}
          <button
            className="primary-button"
            disabled={
              !relationshipForm.targetAssetId ||
              busyAction === "create-relationship" ||
              candidateTargets.length === 0
            }
            type="submit"
          >
            {busyAction === "create-relationship" ? "Linking..." : "Link Asset"}
          </button>
        </form>

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
