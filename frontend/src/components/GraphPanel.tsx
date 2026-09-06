import { useMemo, useCallback } from "react";
import dagre from "@dagrejs/dagre";
import ReactFlow, { Background, MiniMap, Node, Edge, Handle, Position } from "reactflow";
import "reactflow/dist/style.css";
import { GraphData } from "../lib/api";

type Props = {
  graph: GraphData;
  onNodeClick: (filePath: string) => void;
  onExpand?: () => void;
};

function CartographerNode({ data }: { data: { label: string; score: number } }) {
  return (
    <div className={data.score > 50 ? "graphNode isRisky" : "graphNode"}>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      {data.label}
      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </div>
  );
}

const nodeTypes = {
  cartographerNode: CartographerNode,
};

function layoutWithDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 90 });

  nodes.forEach((node) => g.setNode(node.id, { width: 200, height: 50 }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: (pos?.x ?? 0) - 100, y: (pos?.y ?? 0) - 25 },
    };
  });
}

export function GraphPanel({ graph, onNodeClick, onExpand }: Props) {
  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node[] = graph.nodes.map((node) => ({
      id: node.id,
      type: "cartographerNode",
      data: { label: node.label, score: node.score },
      position: { x: 0, y: 0 },
    }));

    const rawEdges: Edge[] = graph.edges.map((edge, i) => ({
      id: `${edge.source}-${edge.target}-${i}`,
      source: edge.source,
      target: edge.target,
      animated: true,
      style: { stroke: 'rgba(255, 255, 255, 0.15)', strokeWidth: 1.5 }
    }));

    const laidNodes = layoutWithDagre(rawNodes, rawEdges);
    return { nodes: laidNodes, edges: rawEdges };
  }, [graph]);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onNodeClick(node.data.label);
  }, [onNodeClick]);

  const totalFiles = graph.total_files ?? nodes.length;
  const truncated = Boolean(graph.truncated);

  return (
    <div className="graphPanel">
      <div className="graphStatsOverlay">
        <span>{nodes.length}{totalFiles > nodes.length ? ` of ${totalFiles}` : ""} files</span>
        <span className="dotSeparator">·</span>
        <span>{edges.length} edges</span>
        {truncated && onExpand && (graph.node_limit ?? 80) < 400 && (
           <button onClick={onExpand} className="ghostButton">Load more</button>
        )}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        minZoom={0.05}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
        elementsSelectable={true}
        nodesConnectable={false}
        nodesDraggable={true}
        panOnScroll={true}
        zoomOnPinch={true}
        preventScrolling={true}
      >
        <Background color="rgba(255,255,255,0.06)" gap={24} size={2} />
        <MiniMap 
          nodeColor={(n) => n.data.score > 50 ? '#f43f5e' : 'rgba(255,255,255,0.3)'}
          maskColor="rgba(0,0,0,0.5)"
          style={{ backgroundColor: 'rgba(10,10,15,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
        />
      </ReactFlow>
    </div>
  );
}
