import React, { useMemo, useCallback, useState } from "react";
import dagre from "@dagrejs/dagre";
import ReactFlow, { Background, MiniMap, Node, Edge, Handle, Position, useReactFlow, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { GraphData } from "../lib/api";
import { GraphToolbar, GraphFilters } from "./GraphToolbar";

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
  is_test_file?: boolean;
  framework?: string;
  is_dead_code?: boolean;
};

function CartographerNode({ data }: { data: NodeData }) {
  const shortName = data.label.split("/").pop();
  const parentDir = data.label.split("/").slice(0, -1).join("/");

  return (
    <div className={`graph-node ${data.isHighRisk ? "high-risk" : ""} ${data.isSelected ? "selected" : ""} ${data.is_dead_code ? "dead-code" : ""}`}>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      <div className="node-content">
        <div className="node-parent">{parentDir}</div>
        <div className="node-name">{shortName}</div>
        <div className="node-meta">
          {data.language && <span>{data.language} · </span>}
          {data.loc !== undefined && <span>{data.loc} LOC</span>}
        </div>
        {data.framework && (
          <div className="node-framework" style={{ fontSize: '10px', color: '#D4AF37' }}>{data.framework}</div>
        )}
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
  g.setGraph({ rankdir: "TB", nodesep: 36, ranksep: 68, ranker: "network-simplex" });

  nodes.forEach((node) => g.setNode(node.id, { width: 196, height: 72 }));
  edges.forEach((edge) => g.setEdge(edge.source, edge.target));

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: (pos?.x ?? 0) - 98, y: (pos?.y ?? 0) - 36 },
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
  const [filters, setFilters] = useState<GraphFilters>({
    hideTests: false,
    highRiskOnly: false,
    hideIsolated: false,
  });
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const { fitView, zoomIn, zoomOut } = useReactFlow();

  const { nodes, edges } = useMemo(() => {
    let rawNodes: Node[] = graph.nodes.map((node) => ({
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
        is_test_file: node.is_test_file,
        framework: node.framework,
        is_dead_code: node.is_dead_code,
      },
      position: { x: 0, y: 0 },
    }));

    if (filters.hideTests) {
      rawNodes = rawNodes.filter(n => !n.data.is_test_file);
    }

    if (filters.highRiskOnly) {
      rawNodes = rawNodes.filter(n => n.data.score > 75);
    }

    const nodeIds = new Set(rawNodes.map(n => n.id));

    let rawEdges: Edge[] = graph.edges
      .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge, i) => ({
        id: `${edge.source}-${edge.target}-${i}`,
        source: edge.source,
        target: edge.target,
        animated: false,
        style: { stroke: 'rgba(255, 255, 255, 0.15)', strokeWidth: 1.5 }
      }));

    if (filters.hideIsolated) {
      const connectedNodes = new Set<string>();
      rawEdges.forEach(e => {
        connectedNodes.add(e.source);
        connectedNodes.add(e.target);
      });
      rawNodes = rawNodes.filter(n => connectedNodes.has(n.id));
      // Rebuild nodeIds
      nodeIds.clear();
      rawNodes.forEach(n => nodeIds.add(n.id));
    }

    const isImpactActive = Boolean(impactMode && impactData);
    const hasSelection = Boolean(selectedFile) || isImpactActive;
    let selectedNeighbors = new Set<string>();

    if (hasSelection) {
      if (isImpactActive && impactData) {
        const labelToId = new Map(rawNodes.map((n) => [n.data.label, n.id]));
        const resolveNodeId = (pathOrId?: string) =>
          pathOrId ? (labelToId.get(pathOrId) ?? pathOrId) : undefined;

        const targetId = resolveNodeId(impactData.target);
        if (targetId) selectedNeighbors.add(targetId);

        impactData.direct_dependents?.forEach((d: string) => {
          const id = resolveNodeId(d);
          if (id) selectedNeighbors.add(id);
        });
        impactData.transitive_dependents?.forEach((d: any) => {
          const id = resolveNodeId(typeof d === "string" ? d : d?.path);
          if (id) selectedNeighbors.add(id);
        });
      } else if (selectedFile) {
        const selectedId = rawNodes.find(n => n.data.label === selectedFile)?.id;
        if (selectedId) {
          selectedNeighbors.add(selectedId);
          rawEdges.forEach(e => {
            if (e.source === selectedId) selectedNeighbors.add(e.target);
            if (e.target === selectedId) selectedNeighbors.add(e.source);
          });
        }
      }

      // Update edges styling for selection
      rawEdges = rawEdges.map((edge) => {
        const isRelated = selectedNeighbors.has(edge.source) && selectedNeighbors.has(edge.target);

        let strokeColor = isRelated ? 'rgba(255, 255, 255, 0.4)' : 'rgba(255, 255, 255, 0.05)';
        if (isImpactActive && isRelated) {
           strokeColor = '#f43f5e';
        }

        return {
          ...edge,
          animated: isImpactActive && isRelated,
          style: { 
            stroke: strokeColor, 
            strokeWidth: isRelated ? 2 : 1.5 
          }
        };
      });
    }

    const laidNodes = layoutWithDagre(rawNodes, rawEdges);
    
    if (hasSelection) {
      laidNodes.forEach(node => {
        if (!selectedNeighbors.has(node.id)) {
          node.style = { opacity: 0.3 };
        } else {
          node.style = { opacity: 1, zIndex: 10 };
          if (isImpactActive && node.data.label !== impactData?.target) {
            node.className = (node.className || "") + " impacted";
          }
        }
      });
    }

    return { nodes: laidNodes, edges: rawEdges };
  }, [graph, selectedFile, impactMode, impactData, filters]);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onNodeClick(node.data.label);
  }, [onNodeClick]);

  return (
    <div className="graph-panel">
      {graph.clusters && graph.clusters.length > 0 && (
        <div className="architecture-scope">
          <span className="scope-label">SCOPE</span>
          <div className="scope-pills">
            {graph.clusters.map(c => (
              <button
                key={c.name}
                className="cluster-btn"
                title={[
                  c.extraction_readiness ? `Extraction readiness: ${c.extraction_readiness}` : null,
                  c.cohesion !== undefined ? `Cohesion: ${c.cohesion} | Coupling: ${c.coupling}` : null,
                ].filter(Boolean).join(" · ") || undefined}
              >
                <span className="cluster-name">{c.name}</span>
                <span className="count">{c.files}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {nodes.length === 0 && (
        <div className="graph-empty-overlay">
          <p>No files match the active graph filters.</p>
          <button
            type="button"
            className="reset-filters-btn"
            onClick={() => setFilters({ hideTests: false, highRiskOnly: false, hideIsolated: false })}
          >
            Reset filters
          </button>
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
        <Background color="rgba(212, 175, 55, 0.06)" gap={24} size={1.5} />
        <MiniMap 
          nodeColor={(n) => n.data.isHighRisk ? '#f43f5e' : n.data.isSelected ? '#D4AF37' : 'rgba(255,255,255,0.24)'}
          maskColor="rgba(9, 9, 11, 0.65)"
          style={{ backgroundColor: 'rgba(17, 17, 19, 0.9)', border: '1px solid rgba(212, 175, 55, 0.16)', borderRadius: '8px' }}
        />
      </ReactFlow>

      {overview && (
        <GraphToolbar
          overview={overview}
          totalFiles={nodes.length}
          totalEdges={edges.length}
          avgRisk={avgRisk || 0}
          onFit={() => fitView({ duration: 800 })}
          onZoomIn={() => zoomIn({ duration: 300 })}
          onZoomOut={() => zoomOut({ duration: 300 })}
          isFilterOpen={isFilterOpen}
          filters={filters}
          onFilterToggle={() => setIsFilterOpen(!isFilterOpen)}
          onFilterChange={setFilters}
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
