import { useMemo, useEffect, useState, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
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

const EDGE_STYLE = { stroke: '#d1d5db', strokeWidth: 1 };
const ORIGIN_EDGE_STYLE = { stroke: '#9ca3af', strokeWidth: 1.5 };
const RECEIVING_EDGE_STYLE = { stroke: '#9ca3af', strokeWidth: 1.5, strokeDasharray: '4 2' };

interface LayoutResult { nodes: Node[]; edges: Edge[] }

function buildLayout(
  graphData: GraphData,
  expandedGroups: Set<string>,
  onToggleExpand: (id: string) => void,
): LayoutResult {
  const groups = graphData.nodes.filter(n => n.type === 'countryGroup');
  const rules = graphData.nodes.filter(n => n.type === 'ruleNode');

  const originEdges = graphData.edges.filter(e => e.data?.relationship === 'TRIGGERED_BY_ORIGIN');
  const receivingEdges = graphData.edges.filter(e => e.data?.relationship === 'TRIGGERED_BY_RECEIVING');

  const originGroupIds = new Set(originEdges.map(e => e.source));
  const receivingGroupIds = new Set(receivingEdges.map(e => e.target));

  const groupOriginEdges: Record<string, typeof originEdges> = {};
  originEdges.forEach(e => { (groupOriginEdges[e.source] ??= []).push(e); });
  const groupReceivingEdges: Record<string, typeof receivingEdges> = {};
  receivingEdges.forEach(e => { (groupReceivingEdges[e.target] ??= []).push(e); });

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Swimlane columns — tight spacing
  const COL_GROUP = 0;
  const COL_COUNTRY = 220;
  const COL_RULE = 420;

  let groupY = 0;
  let countryY = 0;

  // Sort: connected groups first
  const sortedGroups = [...groups].sort((a, b) => {
    const aConn = originGroupIds.has(a.id) || receivingGroupIds.has(a.id) ? 0 : 1;
    const bConn = originGroupIds.has(b.id) || receivingGroupIds.has(b.id) ? 0 : 1;
    return aConn - bConn;
  });

  sortedGroups.forEach(g => {
    const isOrigin = originGroupIds.has(g.id);
    const isReceiving = receivingGroupIds.has(g.id);
    const isExpanded = expandedGroups.has(g.id);
    const countries = (g.data.countries as string[]) || [];
    const hasConnections = isOrigin || isReceiving;

    const collapsedH = 36;
    const expandedH = 36 + countries.length * 20 + 4;
    const groupNodeHeight = isExpanded ? expandedH : collapsedH;

    // Place group node
    nodes.push({
      ...g,
      data: { ...g.data, expanded: isExpanded, onExpand: () => onToggleExpand(g.id) },
      position: { x: COL_GROUP, y: groupY },
    });

    if (isExpanded && hasConnections) {
      const startCountryY = Math.max(countryY, groupY);
      countries.forEach((country) => {
        const countryNodeId = `${g.id}__${country}`;
        nodes.push({
          id: countryNodeId,
          type: 'countryNode',
          data: { label: country, side: isOrigin ? 'origin' : 'receiving' },
          position: { x: COL_COUNTRY, y: countryY },
        });

        // Group → Country edge
        edges.push({
          id: `g2c_${g.id}_${country}`,
          source: g.id, target: countryNodeId,
          type: 'smoothstep', style: EDGE_STYLE,
        });

        // Country → Rule edges (origin)
        if (isOrigin && groupOriginEdges[g.id]) {
          groupOriginEdges[g.id].forEach(oe => {
            edges.push({
              id: `c2r_${countryNodeId}_${oe.target}`,
              source: countryNodeId, target: oe.target,
              type: 'smoothstep', style: ORIGIN_EDGE_STYLE,
            });
          });
        }

        // Rule → Country edges (receiving)
        if (isReceiving && groupReceivingEdges[g.id]) {
          groupReceivingEdges[g.id].forEach(re => {
            edges.push({
              id: `r2c_${re.source}_${countryNodeId}`,
              source: re.source, target: countryNodeId,
              type: 'smoothstep', style: RECEIVING_EDGE_STYLE,
            });
          });
        }

        countryY += 32;
      });

      const countryBlockH = countries.length * 32;
      const advance = Math.max(groupNodeHeight, countryBlockH) + 20;
      groupY += advance;
      if (groupNodeHeight > countryBlockH) {
        countryY = startCountryY + groupNodeHeight + 20;
      } else {
        countryY += 20;
      }
    } else if (!isExpanded && hasConnections) {
      // Collapsed: direct group → rule edges
      if (isOrigin && groupOriginEdges[g.id]) {
        groupOriginEdges[g.id].forEach(oe => {
          edges.push({ id: oe.id, source: g.id, target: oe.target, type: 'smoothstep', style: ORIGIN_EDGE_STYLE });
        });
      }
      if (isReceiving && groupReceivingEdges[g.id]) {
        groupReceivingEdges[g.id].forEach(re => {
          edges.push({ id: re.id, source: re.source, target: g.id, type: 'smoothstep', style: RECEIVING_EDGE_STYLE });
        });
      }
      groupY += collapsedH + 16;
    } else {
      groupY += collapsedH + 12;
    }
  });

  // Place rules centered vertically
  const totalH = Math.max(groupY, countryY);
  const ruleSpacing = 80;
  const totalRulesH = rules.length * ruleSpacing;
  const ruleStartY = Math.max(0, (totalH - totalRulesH) / 2);

  rules.forEach((r, i) => {
    nodes.push({ ...r, position: { x: COL_RULE, y: ruleStartY + i * ruleSpacing } });
  });

  return { nodes, edges };
}

export function RulesNetworkGraph({ data }: { data: GraphData }) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const all = new Set<string>();
    data.nodes.filter(n => n.type === 'countryGroup').forEach(n => all.add(n.id));
    return all;
  });

  const handleToggleExpand = useCallback((groupNodeId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupNodeId)) next.delete(groupNodeId);
      else next.add(groupNodeId);
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
    <div className="flex flex-col w-full h-[calc(100vh-9rem)]">
      {/* Column headers */}
      <div className="flex border-b border-gray-200 mb-0">
        <div style={{ width: 220 }} className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest text-gray-400">Group</div>
        <div style={{ width: 200 }} className="py-2 px-3 text-[10px] font-medium uppercase tracking-widest text-gray-400">Country</div>
        <div className="flex-1 py-2 px-3 text-[10px] font-medium uppercase tracking-widest text-gray-400">Rule</div>
      </div>

      <div className="flex-1 bg-white">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          attributionPosition="bottom-left"
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#f3f4f6" gap={24} size={1} />
          <Controls position="bottom-right" showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
