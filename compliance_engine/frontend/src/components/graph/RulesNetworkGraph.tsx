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

// Edge styles
const ORIGIN_EDGE_STYLE = { stroke: '#D97706', strokeWidth: 2 };
const RECEIVING_EDGE_STYLE = { stroke: '#DC2626', strokeWidth: 2 };

interface LayoutResult {
  nodes: Node[];
  edges: Edge[];
}

function buildLayout(
  graphData: GraphData,
  expandedGroups: Set<string>,
  onToggleExpand: (id: string) => void,
): LayoutResult {
  const groups = graphData.nodes.filter(n => n.type === 'countryGroup');
  const rules = graphData.nodes.filter(n => n.type === 'ruleNode');

  // Build maps of which groups are origin vs receiving
  const originEdges = graphData.edges.filter(e => e.data?.relationship === 'TRIGGERED_BY_ORIGIN');
  const receivingEdges = graphData.edges.filter(e => e.data?.relationship === 'TRIGGERED_BY_RECEIVING');

  const originGroupIds = new Set(originEdges.map(e => e.source));
  const receivingGroupIds = new Set(receivingEdges.map(e => e.target));

  // Map: groupId → rule edges
  const groupOriginEdges: Record<string, typeof originEdges> = {};
  originEdges.forEach(e => {
    (groupOriginEdges[e.source] ??= []).push(e);
  });
  const groupReceivingEdges: Record<string, typeof receivingEdges> = {};
  receivingEdges.forEach(e => {
    (groupReceivingEdges[e.target] ??= []).push(e);
  });

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Column X positions
  const COL_GROUP = 0;
  const COL_COUNTRY = 280;
  const COL_RULE = 560;

  // Track Y positions for each column independently
  let groupY = 0;
  let countryY = 0;

  // Sort groups: origin-only first, then dual, then receiving-only, then unlinked
  const sortedGroups = [...groups].sort((a, b) => {
    const aIsOrigin = originGroupIds.has(a.id);
    const aIsRecv = receivingGroupIds.has(a.id);
    const bIsOrigin = originGroupIds.has(b.id);
    const bIsRecv = receivingGroupIds.has(b.id);
    const aScore = (aIsOrigin ? 0 : 2) + (aIsRecv ? 0 : 0);
    const bScore = (bIsOrigin ? 0 : 2) + (bIsRecv ? 0 : 0);
    return aScore - bScore;
  });

  sortedGroups.forEach(g => {
    const isOrigin = originGroupIds.has(g.id);
    const isReceiving = receivingGroupIds.has(g.id);
    const isExpanded = expandedGroups.has(g.id);
    const countries = (g.data.countries as string[]) || [];
    const hasConnections = isOrigin || isReceiving;

    // Calculate group node height based on expansion
    const groupNodeHeight = isExpanded
      ? 40 + countries.length * 22 + 8
      : 48;

    // Place group node in left column
    nodes.push({
      ...g,
      data: {
        ...g.data,
        expanded: isExpanded,
        onExpand: () => onToggleExpand(g.id),
      },
      position: { x: COL_GROUP, y: groupY },
    });

    if (isExpanded && hasConnections) {
      // Place individual country nodes in center column
      const startCountryY = countryY;
      countries.forEach((country, ci) => {
        const countryNodeId = `${g.id}__${country}`;
        const side = isOrigin ? 'origin' : 'receiving';

        nodes.push({
          id: countryNodeId,
          type: 'countryNode',
          data: { label: country, side },
          position: { x: COL_COUNTRY, y: countryY },
        });

        // Edge: group → country (gold connector)
        edges.push({
          id: `grp2c_${g.id}_${country}`,
          source: g.id,
          target: countryNodeId,
          type: 'smoothstep',
          style: ORIGIN_EDGE_STYLE,
          animated: false,
        });

        // Origin edges: country → rule (gold)
        if (isOrigin && groupOriginEdges[g.id]) {
          groupOriginEdges[g.id].forEach(oe => {
            edges.push({
              id: `c2r_${countryNodeId}_${oe.target}`,
              source: countryNodeId,
              target: oe.target,
              type: 'smoothstep',
              style: ORIGIN_EDGE_STYLE,
              animated: false,
            });
          });
        }

        // Receiving edges: rule → country (red)
        if (isReceiving && groupReceivingEdges[g.id]) {
          groupReceivingEdges[g.id].forEach(re => {
            edges.push({
              id: `r2c_${re.source}_${countryNodeId}`,
              source: re.source,
              target: countryNodeId,
              type: 'smoothstep',
              style: RECEIVING_EDGE_STYLE,
              animated: false,
            });
          });
        }

        countryY += 42;
      });

      // Ensure group column advances enough to match country nodes
      const countryBlockHeight = countries.length * 42;
      const advanceY = Math.max(groupNodeHeight, countryBlockHeight) + 30;
      groupY += advanceY;
      // Only advance countryY if group was taller
      if (groupNodeHeight > countryBlockHeight) {
        countryY = startCountryY + groupNodeHeight + 30;
      } else {
        countryY += 30;
      }
    } else if (!isExpanded && hasConnections) {
      // Collapsed: direct edges from group → rule
      if (isOrigin && groupOriginEdges[g.id]) {
        groupOriginEdges[g.id].forEach(oe => {
          edges.push({
            id: oe.id,
            source: g.id,
            target: oe.target,
            type: 'smoothstep',
            style: ORIGIN_EDGE_STYLE,
            animated: false,
          });
        });
      }
      if (isReceiving && groupReceivingEdges[g.id]) {
        groupReceivingEdges[g.id].forEach(re => {
          edges.push({
            id: re.id,
            source: re.source,
            target: g.id,
            type: 'smoothstep',
            style: RECEIVING_EDGE_STYLE,
            animated: false,
          });
        });
      }
      groupY += groupNodeHeight + 30;
    } else {
      // No connections at all
      groupY += groupNodeHeight + 20;
    }
  });

  // Place rule nodes in right column, spaced evenly
  const totalRulesHeight = rules.length * 120;
  const totalGroupHeight = Math.max(groupY, countryY);
  const ruleStartY = Math.max(0, (totalGroupHeight - totalRulesHeight) / 2);

  rules.forEach((r, i) => {
    nodes.push({
      ...r,
      position: { x: COL_RULE, y: ruleStartY + i * 120 },
    });
  });

  return { nodes, edges };
}

export function RulesNetworkGraph({ data }: { data: GraphData }) {
  // Default all groups to expanded
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const all = new Set<string>();
    data.nodes.filter(n => n.type === 'countryGroup').forEach(n => all.add(n.id));
    return all;
  });

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
    () => buildLayout(data, expandedGroups, handleToggleExpand),
    [data, expandedGroups, handleToggleExpand],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => { setNodes(layoutedNodes); }, [layoutedNodes, setNodes]);
  useEffect(() => { setEdges(layoutedEdges); }, [layoutedEdges, setEdges]);

  return (
    <div className="flex flex-col w-full h-[calc(100vh-10rem)]">
      {/* Column header bar */}
      <div className="flex bg-teal-600 text-white text-sm font-semibold rounded-t-lg overflow-hidden">
        <div className="flex-1 py-2 px-4 text-center border-r border-teal-500">Country Group</div>
        <div className="flex-1 py-2 px-4 text-center border-r border-teal-500">Country</div>
        <div className="flex-1 py-2 px-4 text-center">Rule</div>
      </div>

      {/* Graph canvas */}
      <div className="flex-1 rounded-b-lg border border-t-0 border-gray-200 bg-gray-50">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          attributionPosition="bottom-left"
          minZoom={0.3}
          maxZoom={2}
        >
          <Background color="#e5e7eb" gap={20} />
          <Controls position="bottom-right" />
          <MiniMap
            nodeColor={(n) => {
              if (n.type === 'countryGroup') return '#bfdbfe';
              if (n.type === 'countryNode') return '#fde68a';
              if (n.type === 'ruleNode') return '#fecaca';
              return '#e5e7eb';
            }}
          />
        </ReactFlow>
      </div>
    </div>
  );
}
