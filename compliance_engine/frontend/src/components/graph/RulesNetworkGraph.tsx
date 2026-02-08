import { useMemo, useEffect, useState, useCallback } from 'react';
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
import { CountryNode } from './CountryNode';
import type { GraphData } from '../../types/graph';

const nodeTypes = {
  ruleNode: RuleNode,
  countryGroup: CountrySwimlane,
  countryNode: CountryNode,
};

const defaultEdgeOptions = {
  style: { stroke: '#94a3b8', strokeWidth: 1.5 },
  animated: false,
  type: 'smoothstep' as const,
};

function layoutNodes(
  graphData: GraphData,
  expandedGroups: Set<string>,
  onToggleExpand: (id: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const groups = graphData.nodes.filter(n => n.type === 'countryGroup');
  const rules = graphData.nodes.filter(n => n.type === 'ruleNode');

  // Classify groups into origin vs receiving by checking edges
  const originGroupIds = new Set(
    graphData.edges
      .filter(e => e.data?.relationship === 'TRIGGERED_BY_ORIGIN')
      .map(e => e.source)
  );
  const receivingGroupIds = new Set(
    graphData.edges
      .filter(e => e.data?.relationship === 'TRIGGERED_BY_RECEIVING')
      .map(e => e.target)
  );

  // Groups not in either set go to the left (origin) by default
  const originGroups = groups.filter(g => originGroupIds.has(g.id) || !receivingGroupIds.has(g.id));
  const receivingGroups = groups.filter(g => receivingGroupIds.has(g.id) && !originGroupIds.has(g.id));

  const layoutedNodes: Node[] = [];
  const layoutedEdges: Edge[] = [...graphData.edges];

  // Position origin groups on the left (x=0)
  let originY = 0;
  originGroups.forEach((g) => {
    const isExpanded = expandedGroups.has(g.id);
    if (isExpanded) {
      const countries = (g.data.countries as string[]) || [];
      countries.forEach((country, ci) => {
        const countryNodeId = `${g.id}__country__${country}`;
        layoutedNodes.push({
          id: countryNodeId,
          type: 'countryNode',
          data: { label: country },
          position: { x: 0, y: originY + ci * 40 },
        });
        // Replace edges: find edges that reference this group and duplicate for each country
        graphData.edges.forEach(edge => {
          if (edge.source === g.id) {
            layoutedEdges.push({
              ...edge,
              id: `${edge.id}__${country}`,
              source: countryNodeId,
            });
          }
          if (edge.target === g.id) {
            layoutedEdges.push({
              ...edge,
              id: `${edge.id}__${country}`,
              target: countryNodeId,
            });
          }
        });
      });
      // Remove original edges for this group
      const indicesToRemove: number[] = [];
      layoutedEdges.forEach((edge, i) => {
        if ((edge.source === g.id || edge.target === g.id) && !edge.id.includes('__country__')) {
          indicesToRemove.push(i);
        }
      });
      for (let i = indicesToRemove.length - 1; i >= 0; i--) {
        layoutedEdges.splice(indicesToRemove[i], 1);
      }
      originY += countries.length * 40 + 20;
    } else {
      layoutedNodes.push({
        ...g,
        data: {
          ...g.data,
          expanded: false,
          onExpand: () => onToggleExpand(g.id),
        },
        position: { x: 0, y: originY },
      });
      originY += 120;
    }
  });

  // Position rules in the center (x=400)
  rules.forEach((r, i) => {
    layoutedNodes.push({
      ...r,
      position: { x: 400, y: i * 80 },
    });
  });

  // Position receiving groups on the right (x=800)
  let receivingY = 0;
  receivingGroups.forEach((g) => {
    const isExpanded = expandedGroups.has(g.id);
    if (isExpanded) {
      const countries = (g.data.countries as string[]) || [];
      countries.forEach((country, ci) => {
        const countryNodeId = `${g.id}__country__${country}`;
        layoutedNodes.push({
          id: countryNodeId,
          type: 'countryNode',
          data: { label: country },
          position: { x: 800, y: receivingY + ci * 40 },
        });
        graphData.edges.forEach(edge => {
          if (edge.source === g.id) {
            layoutedEdges.push({
              ...edge,
              id: `${edge.id}__${country}`,
              source: countryNodeId,
            });
          }
          if (edge.target === g.id) {
            layoutedEdges.push({
              ...edge,
              id: `${edge.id}__${country}`,
              target: countryNodeId,
            });
          }
        });
      });
      // Remove original edges for this group
      const indicesToRemove: number[] = [];
      layoutedEdges.forEach((edge, i) => {
        if ((edge.source === g.id || edge.target === g.id) && !edge.id.includes('__country__')) {
          indicesToRemove.push(i);
        }
      });
      for (let i = indicesToRemove.length - 1; i >= 0; i--) {
        layoutedEdges.splice(indicesToRemove[i], 1);
      }
      receivingY += countries.length * 40 + 20;
    } else {
      layoutedNodes.push({
        ...g,
        data: {
          ...g.data,
          expanded: false,
          onExpand: () => onToggleExpand(g.id),
        },
        position: { x: 800, y: receivingY },
      });
      receivingY += 120;
    }
  });

  return { nodes: layoutedNodes, edges: layoutedEdges };
}

export function RulesNetworkGraph({ data }: { data: GraphData }) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const handleToggleExpand = useCallback((groupNodeId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupNodeId)) {
        next.delete(groupNodeId);
      } else {
        next.add(groupNodeId);
      }
      return next;
    });
  }, []);

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => layoutNodes(data, expandedGroups, handleToggleExpand),
    [data, expandedGroups, handleToggleExpand],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Sync nodes/edges when data or expand state changes
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
        defaultEdgeOptions={defaultEdgeOptions}
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
