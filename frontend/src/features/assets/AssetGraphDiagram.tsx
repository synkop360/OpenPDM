import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { formatRelationshipType } from "../../app/format";
import type { AssetGraph } from "../../api";

const RADIUS_STEP = 170;

type LayoutPosition = { id: string; x: number; y: number };

function computeRadialLayout(graph: AssetGraph): LayoutPosition[] {
  const neighbors = new Map<string, Set<string>>();
  const linkTo = (from: string, to: string) => {
    if (!neighbors.has(from)) {
      neighbors.set(from, new Set());
    }
    neighbors.get(from)!.add(to);
  };
  for (const relationship of graph.relationships) {
    linkTo(relationship.source_asset_id, relationship.target_asset_id);
    linkTo(relationship.target_asset_id, relationship.source_asset_id);
  }

  const depthById = new Map<string, number>([[graph.asset_id, 0]]);
  const queue = [graph.asset_id];
  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentDepth = depthById.get(current)!;
    for (const neighbor of neighbors.get(current) ?? []) {
      if (!depthById.has(neighbor)) {
        depthById.set(neighbor, currentDepth + 1);
        queue.push(neighbor);
      }
    }
  }

  const idsByDepth = new Map<number, string[]>();
  for (const node of graph.nodes) {
    const depth = depthById.get(node.id) ?? graph.nodes.length;
    if (!idsByDepth.has(depth)) {
      idsByDepth.set(depth, []);
    }
    idsByDepth.get(depth)!.push(node.id);
  }

  const positions: LayoutPosition[] = [];
  for (const [depth, ids] of idsByDepth) {
    const radius = depth * RADIUS_STEP;
    ids.forEach((id, index) => {
      const angle = (2 * Math.PI * index) / ids.length;
      positions.push({
        id,
        x: depth === 0 ? 0 : radius * Math.cos(angle),
        y: depth === 0 ? 0 : radius * Math.sin(angle),
      });
    });
  }
  return positions;
}

type AssetGraphNodeData = {
  isCenter: boolean;
  label: string;
  status: string;
};

function AssetGraphNode({ data }: NodeProps<Node<AssetGraphNodeData>>) {
  return (
    <div className={data.isCenter ? "asset-graph-node is-center" : "asset-graph-node"}>
      <Handle position={Position.Top} type="target" />
      <strong>{data.label}</strong>
      <small>{data.status}</small>
      <Handle position={Position.Bottom} type="source" />
    </div>
  );
}

const nodeTypes = { assetNode: AssetGraphNode };

type AssetGraphDiagramProps = {
  graph: AssetGraph;
  onSelectAsset: (assetId: string) => void;
};

export function AssetGraphDiagram({ graph, onSelectAsset }: AssetGraphDiagramProps) {
  const nodes = useMemo<Node<AssetGraphNodeData>[]>(() => {
    const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
    return computeRadialLayout(graph)
      .filter((position) => nodesById.has(position.id))
      .map((position) => {
        const graphNode = nodesById.get(position.id)!;
        return {
          id: position.id,
          type: "assetNode",
          position: { x: position.x, y: position.y },
          ariaLabel: `${graphNode.name}, status ${graphNode.status}`,
          data: {
            label: graphNode.name,
            status: graphNode.status,
            isCenter: position.id === graph.asset_id,
          },
        };
      });
  }, [graph]);

  const edges = useMemo<Edge[]>(
    () =>
      graph.relationships.map((relationship) => ({
        id: relationship.id,
        source: relationship.source_asset_id,
        target: relationship.target_asset_id,
        label: formatRelationshipType(relationship.relationship_type),
        markerEnd: { type: MarkerType.ArrowClosed },
      })),
    [graph.relationships],
  );

  return (
    <div className="asset-graph-diagram" role="group" aria-label={`Bounded Asset Graph with ${graph.nodes.length} nodes and ${graph.relationships.length} relationships`}>
      <ReactFlow
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodeTypes={nodeTypes}
        nodes={nodes}
        nodesDraggable
        onNodeClick={(_event, node) => onSelectAsset(node.id)}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
