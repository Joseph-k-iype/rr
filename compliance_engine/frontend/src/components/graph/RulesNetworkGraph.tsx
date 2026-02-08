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

  // A group can appear on both sides if it's both origin and receiving.
  // Duplicate it: once on left (origin) and once on right (receiving).
  const originGroups = groups.filter(g => originGroupIds.has(g.id));
  const receivingGroups = groups.filter(g => receivingGroupIds.has(g.id));
  // Groups not referenced in any edge go to origin side
  const unlinkedGroups = groups.filter(g => !originGroupIds.has(g.id) && !receivingGroupIds.has(g.id));

  const layoutedNodes: Node[] = [];
  // Normalize edges: strip backend "ruleEdge" type so React Flow uses smoothstep default
  const normalizedEdges: Edge[] = graphData.edges.map(e => ({
    ...e,
    type: 'smoothstep',
  }));
  const layoutedEdges: Edge[] = [...normalizedEdges];

  const placeGroups = (
    groupList: typeof groups,
    xPosition: number,
    side: 'origin' | 'receiving',
  ) => {
    let yPos = 0;
    groupList.forEach((g) => {
      // For duplicated groups (both origin and receiving), use a suffixed ID for the receiving copy
      const nodeId = side === 'receiving' && originGroupIds.has(g.id) ? `${g.id}__recv` : g.id;
      const isExpanded = expandedGroups.has(nodeId);

      if (isExpanded) {
        const countries = (g.data.countries as string[]) || [];
        countries.forEach((country, ci) => {
          const countryNodeId = `${nodeId}__country__${country}`;
          layoutedNodes.push({
            id: countryNodeId,
            type: 'countryNode',
            data: { label: country },
            position: { x: xPosition, y: yPos + ci * 40 },
          });
          // Add edges from/to each country node, replacing group edges
          normalizedEdges.forEach(edge => {
            if (edge.source === g.id && (
              (side === 'origin' && edge.data?.relationship === 'TRIGGERED_BY_ORIGIN') ||
              (side === 'receiving')
            )) {
              layoutedEdges.push({
                ...edge,
                id: `${edge.id}__${side}__${country}`,
                source: countryNodeId,
              });
            }
            if (edge.target === g.id && (
              (side === 'receiving' && edge.data?.relationship === 'TRIGGERED_BY_RECEIVING') ||
              (side === 'origin')
            )) {
              layoutedEdges.push({
                ...edge,
                id: `${edge.id}__${side}__${country}`,
                target: countryNodeId,
              });
            }
          });
        });
        // Remove original edges for this group on this side
        const toRemove = new Set<number>();
        layoutedEdges.forEach((edge, i) => {
          if (side === 'origin' && edge.source === g.id && edge.data?.relationship === 'TRIGGERED_BY_ORIGIN' && !edge.id.includes('__country__')) {
            toRemove.add(i);
          }
          if (side === 'receiving' && edge.target === g.id && edge.data?.relationship === 'TRIGGERED_BY_RECEIVING' && !edge.id.includes('__country__')) {
            toRemove.add(i);
          }
        });
        const sorted = Array.from(toRemove).sort((a, b) => b - a);
        for (const idx of sorted) {
          layoutedEdges.splice(idx, 1);
        }
        yPos += countries.length * 40 + 20;
      } else {
        // For receiving-side duplicates, remap edges to use the suffixed node ID
        if (nodeId !== g.id) {
          normalizedEdges.forEach(edge => {
            if (edge.target === g.id && edge.data?.relationship === 'TRIGGERED_BY_RECEIVING') {
              layoutedEdges.push({
                ...edge,
                id: `${edge.id}__recv`,
                target: nodeId,
              });
            }
          });
        }

        layoutedNodes.push({
          ...g,
          id: nodeId,
          data: {
            ...g.data,
            expanded: false,
            onExpand: () => onToggleExpand(nodeId),
          },
          position: { x: xPosition, y: yPos },
        });
        yPos += 120;
      }
    });
  };

  // Left column: origin groups
  placeGroups([...originGroups, ...unlinkedGroups], 0, 'origin');

  // Center column: rules
  rules.forEach((r, i) => {
    layoutedNodes.push({
      ...r,
      position: { x: 400, y: i * 80 },
    });
  });

  // Right column: receiving groups
  placeGroups(receivingGroups, 800, 'receiving');

  // Remove duplicate edges where the original group edge still exists for a duplicated group
  // (receiving copy edges already added above, remove originals pointing to the original ID if a copy exists)
  const finalEdges: Edge[] = [];
  const seenEdgeKeys = new Set<string>();
  for (const edge of layoutedEdges) {
    const key = `${edge.source}->${edge.target}::${edge.data?.relationship || ''}`;
    if (!seenEdgeKeys.has(key)) {
      seenEdgeKeys.add(key);
      finalEdges.push(edge);
    }
  }

  return { nodes: layoutedNodes, edges: finalEdges };
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
