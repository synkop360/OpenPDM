import { Network } from "lucide-react";
import type { AssetGraph } from "../../api";
import type { Loadable } from "../../app/loadable";
import { InlineAlert } from "../../components/feedback/InlineAlert";
import { AssetGraphDiagram } from "./AssetGraphDiagram";

type AssetGraphModeProps = {
  graph: Loadable<AssetGraph | null>;
  onSelectAsset: (assetId: string) => void;
};

/**
 * Full-workspace relationship canvas — the "Graph" half of the asset workspace's
 * Table / Graph toggle. Wraps the shared {@link AssetGraphDiagram} with the
 * project-wide graph's status handling and the standing safety note.
 */
export function AssetGraphMode({ graph, onSelectAsset }: AssetGraphModeProps) {
  const data = graph.data;

  return (
    <section aria-label="Project relationship graph" className="panel asset-panel asset-graph-mode">
      {graph.status === "error" ? (
        <InlineAlert tone="danger">{graph.error}</InlineAlert>
      ) : data && data.nodes.length > 0 ? (
        <>
          <AssetGraphDiagram graph={data} onSelectAsset={onSelectAsset} />
          <p className="muted-text graph-diagram-caption">
            {data.nodes.length} node{data.nodes.length === 1 ? "" : "s"},{" "}
            {data.relationships.length} relationship
            {data.relationships.length === 1 ? "" : "s"} ·{" "}
            {data.has_cycle ? "cycle detected" : "no cycle"}
          </p>
          <p className="muted-text relationship-safety-note">
            Deleting an edge never deletes an Asset. Reference targets outside this Project stay
            unresolved by design.
          </p>
        </>
      ) : graph.status === "loading" ? (
        <p className="empty-state">Loading the project graph…</p>
      ) : (
        <div className="empty-state operational-empty">
          <Network aria-hidden="true" />
          <h3>No relationships to graph</h3>
          <p>Assets in this Project have no relationships yet. Link two Assets to see them here.</p>
        </div>
      )}
    </section>
  );
}
