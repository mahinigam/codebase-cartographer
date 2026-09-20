import React, { useMemo, useCallback } from "react";
import dagre from "@dagrejs/dagre";
import ReactFlow, { Background, MiniMap, Node, Edge, Handle, Position, useReactFlow, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { GraphData } from "../lib/api";
import { GraphToolbar } from "./GraphToolbar";

type Props = {
  graph: GraphData;
  selectedFile?: string | null;
  impactMode?: boolean;
  impactData?: any;
  onNodeClick: (filePath: string) => void;
  onExpand?: () => void;
  overview?: any;
  totalFiles?: number;
  totalEdges?: number;
  avgRisk?: number;
  onFilterToggle?: () => void;
};

type NodeData = {
  label: string;
  score: number;
  language?: string;
  loc?: number;
  dependents?: number;
  isHighRisk?: boolean;
  isSelected?: boolean;
};

function CartographerNode({ data }: { data: NodeData }) {
  const shortName = data.label.split("/").pop();
  const parentDir = data.label.split("/").slice(0, -1).join("/");

  return (
    <div className={`graph-node ${data.isHighRisk ? "high-risk" : ""} ${data.isSelected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      <div className="node-content">
        <div className="node-parent">{parentDir}</div>
        <div className="node-name">{shortName}</div>
        <div className="node-meta">
          {data.language && <span>{data.language} · </span>}
          {data.loc !== undefined && <span>{data.loc} LOC</span>}
        </div>
        {data.dependents !== undefined && data.dependents > 0 && (
          <div className="node-deps">{data.dependents} dependents</div>
        )}
      </div>
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

  nodes.forEach((node) => g.setNode(node.id, { width: 220, height: 80 }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: (pos?.x ?? 0) - 110, y: (pos?.y ?? 0) - 40 },
    };
  });
}

function GraphPanelContent({ 
  graph, 
  selectedFile, 
  impactMode, 
  impactData, 
  onNodeClick, 
  onExpand,
  overview,
  totalFiles,
  totalEdges,
  avgRisk,
  onFilterToggle
}: Props) {
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node[] = graph.nodes.map((node) => ({
      id: node.id,
      type: "cartographerNode",
      data: { 
        label: node.label, 
        score: node.score,
        language: node.language,
        loc: node.loc,
        dependents: node.fan_in,
        isHighRisk: node.score > 75,
        isSelected: selectedFile === node.label,
      },
      position: { x: 0, y: 0 },
    }));

    const hasSelection = Boolean(selectedFile) || impactMode;
    let selectedNeighbors = new Set<string>();
    
    if (impactMode && impactData) {
      selectedNeighbors.add(impactData.target);
      impactData.direct_dependents.forEach((d: string) => selectedNeighbors.add(d));
      impactData.transitive_dependents.forEach((d: any) => selectedNeighbors.add(d.path));
    } else if (selectedFile) {
      const selectedId = rawNodes.find(n => n.data.label === selectedFile)?.id;
      if (selectedId) {
        selectedNeighbors.add(selectedId);
        graph.edges.forEach(e => {
          if (e.source === selectedId) selectedNeighbors.add(e.target);
          if (e.target === selectedId) selectedNeighbors.add(e.source);
        });
      }
    }

    const rawEdges: Edge[] = graph.edges.map((edge, i) => {
      const isRelated = selectedNeighbors.has(edge.source) && selectedNeighbors.has(edge.target);
      const isDimmed = hasSelection && !isRelated;

      let strokeColor = isRelated ? 'rgba(255, 255, 255, 0.4)' : (isDimmed ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.15)');
      if (impactMode && isRelated) {
         strokeColor = '#f43f5e';
      }

      return {
        id: `${edge.source}-${edge.target}-${i}`,
        source: edge.source,
        target: edge.target,
        animated: impactMode && isRelated,
        style: { 
          stroke: strokeColor, 
          strokeWidth: isRelated ? 2 : 1.5 
        }
      };
    });

    const laidNodes = layoutWithDagre(rawNodes, rawEdges);
    
    if (hasSelection) {
      laidNodes.forEach(node => {
        if (!selectedNeighbors.has(node.id)) {
          node.style = { opacity: 0.3 };
        } else {
          node.style = { opacity: 1, zIndex: 10 };
          if (impactMode && node.data.label !== impactData?.target) {
            node.className = (node.className || "") + " impacted";
          }
        }
      });
    }

    return { nodes: laidNodes, edges: rawEdges };
  }, [graph, selectedFile, impactMode, impactData]);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onNodeClick(node.data.label);
  }, [onNodeClick]);

  return (
    <div className="graph-panel">
      {graph.clusters && graph.clusters.length > 0 && (
        <div className="architecture-scope">
          <span className="scope-label">ARCHITECTURE SCOPE</span>
          {graph.clusters.map(c => (
            <button key={c.name} className="cluster-btn">
              {c.name} <span className="count">{c.files}</span>
            </button>
          ))}
        </div>
      )}

      <ReactFlow
        style={{ width: '100%', height: '100%' }}
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
          nodeColor={(n) => n.data.isHighRisk ? '#f43f5e' : 'rgba(255,255,255,0.3)'}
          maskColor="rgba(0,0,0,0.5)"
          style={{ backgroundColor: 'rgba(10,10,15,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
        />
      </ReactFlow>

      {overview && (
        <GraphToolbar
          overview={overview}
          totalFiles={totalFiles || 0}
          totalEdges={totalEdges || 0}
          avgRisk={avgRisk || 0}
          onFit={() => fitView({ duration: 800 })}
          onZoomIn={() => zoomIn({ duration: 300 })}
          onZoomOut={() => zoomOut({ duration: 300 })}
          onFilterToggle={onFilterToggle || (() => {})}
        />
      )}
    </div>
  );
}

export function GraphPanel(props: Props) {
  return (
    <ReactFlowProvider>
      <GraphPanelContent {...props} />
    </ReactFlowProvider>
  );
}
