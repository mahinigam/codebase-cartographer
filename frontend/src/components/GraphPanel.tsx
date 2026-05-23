import { useMemo } from "react";
import ReactFlow, { Background, Controls, Node, Edge } from "reactflow";
import dagre from "@dagrejs/dagre";
import { GraphData } from "../lib/api";

type Props = {
  graph: GraphData;
  onNodeClick: (filePath: string) => void;
};

function layoutWithDagre(
  nodes: Node[],
  edges: Edge[]
): Node[] {
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

export function GraphPanel({ graph, onNodeClick }: Props) {
  const flow = useMemo(() => {
    const rawNodes: Node[] = graph.nodes.map((node) => ({
      id: node.id,
      data: { label: node.label },
      position: { x: 0, y: 0 },
      style: {
        border: node.score > 70 ? "2px solid #e11d48" : "1px solid #26364f",
        background: node.score > 70 ? "#fff1f2" : "#f8fafc",
        color: "#172033",
        borderRadius: 10,
        width: 200,
        fontSize: 12,
        fontWeight: node.score > 50 ? 600 : 400,
        cursor: "pointer",
      },
    }));
    const rawEdges: Edge[] = graph.edges.map((edge, i) => ({
      id: `${edge.source}-${edge.target}-${i}`,
      source: edge.source,
      target: edge.target,
      animated: false,
      style: { stroke: "#94a3b8", strokeWidth: 1.5 },
    }));

    const laid = layoutWithDagre(rawNodes, rawEdges);
    return { nodes: laid, edges: rawEdges };
  }, [graph]);

  return (
    <div className="graphPanel">
      <div className="panelHeader">
        <h2>Architecture Graph</h2>
        <span>
          {flow.nodes.length} nodes · {flow.edges.length} edges
        </span>
      </div>
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        fitView
        onNodeClick={(_, node) => onNodeClick(node.data.label)}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
