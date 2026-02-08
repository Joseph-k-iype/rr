import { useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { RuleNode } from './RuleNode';
import { CountrySwimlane } from './CountrySwimlane';
import type { GraphData } from '../../types/graph';

const nodeTypes = {
  ruleNode: RuleNode,
  countryGroup: CountrySwimlane,
};

function layoutNodes(graphData: GraphData): { nodes: Node[]; edges: Edge[] } {
  const groups = graphData.nodes.filter(n => n.type === 'countryGroup');
  const rules = graphData.nodes.filter(n => n.type === 'ruleNode');

  const layoutedNodes: Node[] = [];

  // Position groups vertically on left side
  groups.forEach((g, i) => {
    layoutedNodes.push({
      ...g,
      position: { x: 50, y: i * 120 },
    });
  });

  // Position rules in the center
  rules.forEach((r, i) => {
    layoutedNodes.push({
      ...r,
      position: { x: 400, y: i * 80 },
    });
  });

  return { nodes: layoutedNodes, edges: graphData.edges };
}

export function RulesNetworkGraph({ data }: { data: GraphData }) {
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => layoutNodes(data), [data]);
  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Sync nodes/edges when data changes
  useEffect(() => { setNodes(layoutedNodes); }, [layoutedNodes, setNodes]);
  useEffect(() => { setEdges(layoutedEdges); }, [layoutedEdges, setEdges]);

  return (
    <div className="w-full h-[calc(100vh-8rem)] rounded-lg border border-gray-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color="#f0f0f0" gap={16} />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
