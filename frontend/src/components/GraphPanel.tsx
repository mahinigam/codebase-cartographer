import { useMemo } from "react";
import dagre from "@dagrejs/dagre";
import { GraphData } from "../lib/api";

type Props = {
  graph: GraphData;
  onNodeClick: (filePath: string) => void;
  onExpand?: () => void;
};

type GraphNode = {
  id: string;
  label: string;
  score: number;
  position: { x: number; y: number };
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

function layoutWithDagre(
  nodes: GraphNode[],
  edges: GraphEdge[]
): GraphNode[] {
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
  const flow = useMemo(() => {
    const rawNodes: GraphNode[] = graph.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      score: node.score,
      position: { x: 0, y: 0 },
    }));
    const rawEdges: GraphEdge[] = graph.edges.map((edge, i) => ({
      id: `${edge.source}-${edge.target}-${i}`,
      source: edge.source,
      target: edge.target,
    }));

    const laid = layoutWithDagre(rawNodes, rawEdges);
    const maxX = Math.max(0, ...laid.map((node) => node.position.x + 220));
    const maxY = Math.max(0, ...laid.map((node) => node.position.y + 70));
    return { nodes: laid, edges: rawEdges, width: maxX + 40, height: maxY + 40 };
  }, [graph]);

  const nodesById = useMemo(
    () => new Map(flow.nodes.map((node) => [node.id, node])),
    [flow.nodes]
  );

  const totalFiles = graph.total_files ?? flow.nodes.length;
  const truncated = Boolean(graph.truncated);

  return (
    <div className="graphPanel">
      <div className="panelHeader">
        <h2>Architecture Graph</h2>
        <div className="graphHeaderMeta">
          <span>
            {flow.nodes.length}
            {totalFiles > flow.nodes.length ? ` of ${totalFiles}` : ""} files ·{" "}
            {flow.edges.length} edges
          </span>
          {truncated && onExpand && (graph.node_limit ?? 80) < 400 ? (
            <button type="button" className="ghostButton" onClick={onExpand}>
              Show more
            </button>
          ) : null}
        </div>
      </div>
      {truncated ? (
        <p className="graphTruncationNote">
          Showing the highest load-bearing files so the view stays usable. Expand to
          load more of the graph.
        </p>
      ) : null}
      <div className="graphViewport">
        <div
          className="graphCanvas"
          style={{ width: flow.width, height: flow.height }}
        >
          <svg
            aria-hidden="true"
            className="graphEdges"
            width={flow.width}
            height={flow.height}
          >
            {flow.edges.map((edge) => {
              const source = nodesById.get(edge.source);
              const target = nodesById.get(edge.target);
              if (!source || !target) return null;
              const x1 = source.position.x + 100;
              const y1 = source.position.y + 50;
              const x2 = target.position.x + 100;
              const y2 = target.position.y;
              return (
                <line
                  key={edge.id}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </svg>
          {flow.nodes.map((node) => (
            <button
              key={node.id}
              className={node.score > 50 ? "graphNode isRisky" : "graphNode"}
              style={{
                left: node.position.x,
                top: node.position.y,
              }}
              onClick={() => onNodeClick(node.label)}
            >
              {node.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
