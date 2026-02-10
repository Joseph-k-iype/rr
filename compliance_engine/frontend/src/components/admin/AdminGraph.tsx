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
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { RuleNode } from '../graph/RuleNode';
import { CountrySwimlane } from '../graph/CountrySwimlane';
import { AdminSwimlane } from './AdminSwimlane';
import { ContextMenu, type ContextMenuAction } from './ContextMenu';
import { EditModal } from './EditModal';
import {
  getAdminRules,
  getCountryGroups,
  getDictionaryEntries,
  updateAdminRule,
  deleteAdminRule,
  deleteCountryGroup,
  deleteDictionaryEntry,
  type DictType,
} from '../../services/adminApi';
import { LoadingSpinner } from '../common/LoadingSpinner';

const nodeTypes = {
  ruleNode: RuleNode,
  countryGroup: CountrySwimlane,
  adminNode: AdminSwimlane,
};

const EDGE_STYLE = { stroke: '#d1d5db', strokeWidth: 1 };

interface LaneConfig {
  key: string;
  label: string;
  width: number;
}

const LANES: LaneConfig[] = [
  { key: 'groups', label: 'Country Groups', width: 200 },
  { key: 'rules', label: 'Rules', width: 240 },
  { key: 'processes', label: 'Processes', width: 160 },
  { key: 'purposes', label: 'Purposes', width: 160 },
  { key: 'subjects_gdc', label: 'Subjects / GDC', width: 160 },
];

interface ContextState {
  x: number;
  y: number;
  nodeId: string;
  nodeType: string;
  nodeData: Record<string, unknown>;
}

interface EditState {
  title: string;
  fields: { key: string; label: string; value: string; type?: string }[];
  onSave: (values: Record<string, string>) => void;
}

export function AdminGraph() {
  const queryClient = useQueryClient();
  const [collapsedLanes, setCollapsedLanes] = useState<Set<string>>(new Set());
  const [contextMenu, setContextMenu] = useState<ContextState | null>(null);
  const [editModal, setEditModal] = useState<EditState | null>(null);

  const { data: rules, isLoading: rulesLoading } = useQuery({ queryKey: ['admin-rules'], queryFn: getAdminRules });
  const { data: groups, isLoading: groupsLoading } = useQuery({ queryKey: ['admin-groups'], queryFn: getCountryGroups });
  const { data: processes } = useQuery({ queryKey: ['admin-dict-processes'], queryFn: () => getDictionaryEntries('processes') });
  const { data: purposes } = useQuery({ queryKey: ['admin-dict-purposes'], queryFn: () => getDictionaryEntries('purposes') });
  const { data: dataSubjects } = useQuery({ queryKey: ['admin-dict-data_subjects'], queryFn: () => getDictionaryEntries('data_subjects') });
  const { data: gdc } = useQuery({ queryKey: ['admin-dict-gdc'], queryFn: () => getDictionaryEntries('gdc') });

  const isLoading = rulesLoading || groupsLoading;

  const toggleLane = useCallback((key: string) => {
    setCollapsedLanes(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin-rules'] });
    queryClient.invalidateQueries({ queryKey: ['admin-groups'] });
    queryClient.invalidateQueries({ queryKey: ['admin-dict-processes'] });
    queryClient.invalidateQueries({ queryKey: ['admin-dict-purposes'] });
    queryClient.invalidateQueries({ queryKey: ['admin-dict-data_subjects'] });
    queryClient.invalidateQueries({ queryKey: ['admin-dict-gdc'] });
  }, [queryClient]);

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Compute lane X positions
    let xOffset = 0;
    const laneX: Record<string, number> = {};
    for (const lane of LANES) {
      if (collapsedLanes.has(lane.key)) {
        laneX[lane.key] = xOffset;
        xOffset += 30;
      } else {
        laneX[lane.key] = xOffset;
        xOffset += lane.width + 20;
      }
    }

    // Lane 1: Country Groups
    if (!collapsedLanes.has('groups') && groups) {
      (groups as { name: string; countries: string[] }[]).forEach((g, i) => {
        const id = `group_${g.name}`;
        nodes.push({
          id,
          type: 'countryGroup',
          data: { label: g.name, countries: g.countries, country_count: g.countries?.length ?? 0, expanded: false },
          position: { x: laneX['groups'], y: i * 44 },
        });
      });
    }

    // Lane 2: Rules
    if (!collapsedLanes.has('rules') && rules) {
      (rules as Record<string, unknown>[]).forEach((r, i) => {
        const id = `rule_${r.rule_id}`;
        nodes.push({
          id,
          type: 'ruleNode',
          data: {
            label: r.name,
            rule_id: r.rule_id,
            priority: r.priority,
            odrl_type: r.odrl_type,
            outcome: r.outcome,
          },
          position: { x: laneX['rules'], y: i * 80 },
        });

        // Edges from origin groups to rules
        const originScopes = (r.origin_scopes as string[]) || [];
        originScopes.forEach(scope => {
          if (scope) {
            edges.push({
              id: `e_o_${scope}_${r.rule_id}`,
              source: `group_${scope}`,
              target: id,
              type: 'smoothstep',
              style: EDGE_STYLE,
            });
          }
        });

        // Edges from rules to receiving groups
        const receivingScopes = (r.receiving_scopes as string[]) || [];
        receivingScopes.forEach(scope => {
          if (scope) {
            edges.push({
              id: `e_r_${r.rule_id}_${scope}`,
              source: id,
              target: `group_${scope}`,
              type: 'smoothstep',
              style: { ...EDGE_STYLE, strokeDasharray: '4 2' },
            });
          }
        });
      });
    }

    // Lane 3: Processes
    if (!collapsedLanes.has('processes') && processes) {
      (processes as { name: string; category: string }[]).forEach((p, i) => {
        nodes.push({
          id: `proc_${p.name}`,
          type: 'adminNode',
          data: { label: p.name, category: p.category, dictType: 'processes' },
          position: { x: laneX['processes'], y: i * 32 },
        });
      });
    }

    // Lane 4: Purposes
    if (!collapsedLanes.has('purposes') && purposes) {
      (purposes as { name: string; category: string }[]).forEach((p, i) => {
        nodes.push({
          id: `purp_${p.name}`,
          type: 'adminNode',
          data: { label: p.name, category: p.category, dictType: 'purposes' },
          position: { x: laneX['purposes'], y: i * 32 },
        });
      });
    }

    // Lane 5: DataSubjects + GDC
    if (!collapsedLanes.has('subjects_gdc')) {
      let y = 0;
      if (dataSubjects) {
        (dataSubjects as { name: string; category: string }[]).forEach((d) => {
          nodes.push({
            id: `ds_${d.name}`,
            type: 'adminNode',
            data: { label: d.name, category: d.category, dictType: 'data_subjects' },
            position: { x: laneX['subjects_gdc'], y },
          });
          y += 32;
        });
      }
      if (gdc) {
        y += 16; // gap between subjects and gdc
        (gdc as { name: string; category: string }[]).forEach((g) => {
          nodes.push({
            id: `gdc_${g.name}`,
            type: 'adminNode',
            data: { label: g.name, category: g.category, dictType: 'gdc' },
            position: { x: laneX['subjects_gdc'], y },
          });
          y += 32;
        });
      }
    }

    return { nodes, edges };
  }, [rules, groups, processes, purposes, dataSubjects, gdc, collapsedLanes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [graphEdges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  useEffect(() => { setNodes(layoutNodes); }, [layoutNodes, setNodes]);
  useEffect(() => { setEdges(layoutEdges); }, [layoutEdges, setEdges]);

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      nodeId: node.id,
      nodeType: node.type || '',
      nodeData: node.data as Record<string, unknown>,
    });
  }, []);

  const getContextActions = useCallback((): ContextMenuAction[] => {
    if (!contextMenu) return [];
    const { nodeType, nodeData, nodeId } = contextMenu;

    if (nodeType === 'ruleNode') {
      const ruleId = String(nodeData.rule_id || '');
      return [
        {
          label: 'Edit Rule',
          onClick: () => {
            setEditModal({
              title: `Edit Rule: ${ruleId}`,
              fields: [
                { key: 'name', label: 'Name', value: String(nodeData.label || '') },
                { key: 'description', label: 'Description', value: '', type: 'textarea' },
                { key: 'priority', label: 'Priority', value: String(nodeData.priority || 'medium') },
              ],
              onSave: async (vals) => {
                await updateAdminRule(ruleId, vals);
                invalidateAll();
              },
            });
          },
        },
        {
          label: 'Delete Rule',
          danger: true,
          onClick: async () => {
            await deleteAdminRule(ruleId);
            invalidateAll();
          },
        },
      ];
    }

    if (nodeType === 'countryGroup') {
      const groupName = String(nodeData.label || '');
      return [
        {
          label: 'Delete Group',
          danger: true,
          onClick: async () => {
            await deleteCountryGroup(groupName);
            invalidateAll();
          },
        },
      ];
    }

    if (nodeType === 'adminNode') {
      const dictType = String(nodeData.dictType || '') as DictType;
      const entryName = String(nodeData.label || '');
      return [
        {
          label: 'Delete Entry',
          danger: true,
          onClick: async () => {
            await deleteDictionaryEntry(dictType, entryName);
            invalidateAll();
          },
        },
      ];
    }

    return [];
  }, [contextMenu, invalidateAll]);

  if (isLoading) return <LoadingSpinner message="Loading admin graph..." />;

  return (
    <>
      <div className="flex flex-col w-full h-[calc(100vh-9rem)]">
        {/* Column headers */}
        <div className="flex border-b border-gray-200 mb-0">
          {LANES.map(lane => (
            <div
              key={lane.key}
              style={{ width: collapsedLanes.has(lane.key) ? 30 : lane.width + 20 }}
              className="py-2 px-2 text-[10px] font-medium uppercase tracking-widest text-gray-400 cursor-pointer select-none hover:text-gray-600 transition-colors"
              onClick={() => toggleLane(lane.key)}
              title={collapsedLanes.has(lane.key) ? `Expand ${lane.label}` : `Collapse ${lane.label}`}
            >
              {collapsedLanes.has(lane.key) ? (
                <span className="writing-mode-vertical text-[9px]">{lane.label.charAt(0)}</span>
              ) : (
                lane.label
              )}
            </div>
          ))}
        </div>

        <div className="flex-1 bg-white">
          <ReactFlow
            nodes={nodes}
            edges={graphEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            onNodeContextMenu={handleNodeContextMenu}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            attributionPosition="bottom-left"
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#f3f4f6" gap={24} size={1} />
            <Controls position="bottom-right" showInteractive={false} />
          </ReactFlow>
        </div>
      </div>

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          actions={getContextActions()}
          onClose={() => setContextMenu(null)}
        />
      )}

      {editModal && (
        <EditModal
          title={editModal.title}
          fields={editModal.fields}
          onSave={editModal.onSave}
          onClose={() => setEditModal(null)}
        />
      )}
    </>
  );
}
