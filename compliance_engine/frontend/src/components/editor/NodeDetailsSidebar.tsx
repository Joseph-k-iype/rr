import { memo, useMemo, useState, useCallback } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useEditorStore } from '../../stores/editorStore';

const NODE_TYPE_COLORS: Record<string, string> = {
  Rule: 'bg-red-100 text-red-700',
  Country: 'bg-sky-100 text-sky-700',
  CountryGroup: 'bg-blue-100 text-blue-700',
  DataCategory: 'bg-emerald-100 text-emerald-700',
  Purpose: 'bg-amber-100 text-amber-700',
  Process: 'bg-cyan-100 text-cyan-700',
  GDC: 'bg-purple-100 text-purple-700',
  Duty: 'bg-teal-100 text-teal-700',
  Action: 'bg-teal-100 text-teal-700',
  Permission: 'bg-green-100 text-green-700',
  Prohibition: 'bg-red-100 text-red-700',
  LegalEntity: 'bg-orange-100 text-orange-700',
  DataSubject: 'bg-pink-100 text-pink-700',
  Attribute: 'bg-violet-100 text-violet-700',
};

const PROTECTED_RELATIONSHIPS = new Set([
  'TRIGGERED_BY_ORIGIN',
  'TRIGGERED_BY_RECEIVING',
  'BELONGS_TO',
  'EXCLUDES_RECEIVING',
]);

function NodeDetailsSidebarInner() {
  const sidebarNodeId = useEditorStore((s) => s.sidebarNodeId);
  const closeSidebar = useEditorStore((s) => s.closeSidebar);
  const nodes = useEditorStore((s) => s.visibleNodes);
  const edges = useEditorStore((s) => s.visibleEdges);
  const openSidebar = useEditorStore((s) => s.openSidebar);
  const updateNodeData = useEditorStore((s) => s.updateNodeData);
  const removeNode = useEditorStore((s) => s.removeNode);
  const removeEdge = useEditorStore((s) => s.removeEdge);
  const { setCenter } = useReactFlow();

  const [editMode, setEditMode] = useState(false);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const node = useMemo(
    () => nodes.find((n) => n.id === sidebarNodeId),
    [nodes, sidebarNodeId]
  );

  const connections = useMemo(() => {
    if (!sidebarNodeId) return { incoming: [], outgoing: [] };
    const incoming: { nodeId: string; edgeId: string; label: string; nodeType: string; relationship: string }[] = [];
    const outgoing: { nodeId: string; edgeId: string; label: string; nodeType: string; relationship: string }[] = [];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    for (const edge of edges) {
      if (edge.target === sidebarNodeId) {
        const src = nodeMap.get(edge.source);
        if (src) {
          incoming.push({
            nodeId: src.id,
            edgeId: edge.id,
            label: (src.data as { label?: string })?.label || src.id,
            nodeType: (src.data as { nodeType?: string })?.nodeType || '',
            relationship: (edge.data as { relationship?: string })?.relationship || '',
          });
        }
      }
      if (edge.source === sidebarNodeId) {
        const tgt = nodeMap.get(edge.target);
        if (tgt) {
          outgoing.push({
            nodeId: tgt.id,
            edgeId: edge.id,
            label: (tgt.data as { label?: string })?.label || tgt.id,
            nodeType: (tgt.data as { nodeType?: string })?.nodeType || '',
            relationship: (edge.data as { relationship?: string })?.relationship || '',
          });
        }
      }
    }

    return { incoming, outgoing };
  }, [sidebarNodeId, nodes, edges]);

  const enterEditMode = useCallback(() => {
    if (!node) return;
    const data = node.data as unknown as Record<string, unknown>;
    const skipKeys = new Set(['nodeType', 'lane']);
    const vals: Record<string, string> = {};
    for (const [k, v] of Object.entries(data)) {
      if (!skipKeys.has(k) && v !== undefined && v !== null) {
        vals[k] = Array.isArray(v) ? v.join(', ') : String(v);
      }
    }
    setEditValues(vals);
    setEditMode(true);
  }, [node]);

  const handleSave = useCallback(async () => {
    if (!sidebarNodeId) return;
    setSaving(true);
    try {
      await updateNodeData(sidebarNodeId, editValues);
      setEditMode(false);
    } finally {
      setSaving(false);
    }
  }, [sidebarNodeId, editValues, updateNodeData]);

  const handleDeleteNode = useCallback(async () => {
    if (!sidebarNodeId || !node) return;
    // Check for protected relationships
    const hasProtected = edges.some(
      (e) =>
        (e.source === sidebarNodeId || e.target === sidebarNodeId) &&
        PROTECTED_RELATIONSHIPS.has((e.data as { relationship?: string })?.relationship || '')
    );
    if (hasProtected) {
      alert('Cannot delete node with protected relationships.');
      return;
    }
    const label = (node.data as { label?: string })?.label || sidebarNodeId;
    if (confirm(`Delete node "${label}"? This action cannot be undone.`)) {
      closeSidebar();
      await removeNode(sidebarNodeId);
    }
  }, [sidebarNodeId, node, edges, closeSidebar, removeNode]);

  const handleDeleteEdge = useCallback(async (edgeId: string, relationship: string) => {
    if (PROTECTED_RELATIONSHIPS.has(relationship)) {
      alert('Cannot delete protected relationship.');
      return;
    }
    if (confirm(`Delete edge "${relationship}"?`)) {
      await removeEdge(edgeId);
    }
  }, [removeEdge]);

  if (!sidebarNodeId || !node) return null;

  const data = node.data as unknown as Record<string, unknown>;
  const nodeType = (data.nodeType as string) || '';
  const label = (data.label as string) || node.id;
  const badgeColor = NODE_TYPE_COLORS[nodeType] || 'bg-gray-100 text-gray-700';

  // Properties to show (exclude internal ones)
  const skipKeys = new Set(['label', 'nodeType', 'lane']);
  const properties = Object.entries(data).filter(
    ([k, v]) => !skipKeys.has(k) && v !== undefined && v !== null && v !== ''
  );

  const navigateToNode = (nodeId: string) => {
    const target = nodes.find((n) => n.id === nodeId);
    if (target) {
      setCenter(target.position.x + 110, target.position.y + 30, { zoom: 1.2, duration: 400 });
    }
    openSidebar(nodeId);
  };

  return (
    <div className="w-80 bg-white border-l border-gray-200 overflow-y-auto flex flex-col shadow-lg">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-gray-100">
        <div className="flex-1 min-w-0">
          <span className={`inline-block px-2 py-0.5 text-[10px] font-semibold rounded-full mb-1.5 ${badgeColor}`}>
            {nodeType}
          </span>
          <h3 className="text-sm font-semibold text-gray-800 truncate">{label}</h3>
        </div>
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={editMode ? () => setEditMode(false) : enterEditMode}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              editMode ? 'bg-gray-200 text-gray-700' : 'text-gray-500 hover:bg-gray-100'
            }`}
            title={editMode ? 'Cancel edit' : 'Edit node'}
          >
            {editMode ? 'Cancel' : '✎'}
          </button>
          <button
            onClick={closeSidebar}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          >
            &times;
          </button>
        </div>
      </div>

      {/* Properties */}
      {editMode ? (
        <div className="p-4 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Edit Properties</h4>
          <div className="space-y-2">
            {Object.entries(editValues).map(([key, value]) => (
              <div key={key} className="flex flex-col">
                <label className="text-[10px] text-gray-400 mb-0.5">{key}</label>
                <input
                  type="text"
                  value={value}
                  onChange={(e) =>
                    setEditValues((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  className="text-xs text-gray-700 border border-gray-200 rounded px-2 py-1 focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-500 rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={handleDeleteNode}
              className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      ) : (
        properties.length > 0 && (
          <div className="p-4 border-b border-gray-100">
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Properties</h4>
            <dl className="space-y-1.5">
              {properties.map(([key, value]) => (
                <div key={key} className="flex flex-col">
                  <dt className="text-[10px] text-gray-400">{key}</dt>
                  <dd className="text-xs text-gray-700 break-words">
                    {Array.isArray(value) ? value.join(', ') : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )
      )}

      {/* Incoming connections */}
      {connections.incoming.length > 0 && (
        <div className="p-4 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
            Incoming ({connections.incoming.length})
          </h4>
          <ul className="space-y-1">
            {connections.incoming.map((conn, i) => (
              <li key={i} className="flex items-center justify-between">
                <button
                  onClick={() => navigateToNode(conn.nodeId)}
                  className="flex-1 text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded px-1.5 py-1 transition-colors truncate"
                >
                  <span className="text-gray-400 text-[10px]">{conn.relationship}</span>{' '}
                  <span className="font-medium">{conn.label}</span>
                  <span className="text-gray-400 text-[10px] ml-1">({conn.nodeType})</span>
                </button>
                {PROTECTED_RELATIONSHIPS.has(conn.relationship) ? (
                  <span className="text-[9px] text-gray-400 px-1">protected</span>
                ) : (
                  <button
                    onClick={() => handleDeleteEdge(conn.edgeId, conn.relationship)}
                    className="text-red-400 hover:text-red-600 text-[10px] px-1"
                    title="Delete edge"
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Outgoing connections */}
      {connections.outgoing.length > 0 && (
        <div className="p-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
            Outgoing ({connections.outgoing.length})
          </h4>
          <ul className="space-y-1">
            {connections.outgoing.map((conn, i) => (
              <li key={i} className="flex items-center justify-between">
                <button
                  onClick={() => navigateToNode(conn.nodeId)}
                  className="flex-1 text-left text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded px-1.5 py-1 transition-colors truncate"
                >
                  <span className="text-gray-400 text-[10px]">{conn.relationship}</span>{' '}
                  <span className="font-medium">{conn.label}</span>
                  <span className="text-gray-400 text-[10px] ml-1">({conn.nodeType})</span>
                </button>
                {PROTECTED_RELATIONSHIPS.has(conn.relationship) ? (
                  <span className="text-[9px] text-gray-400 px-1">protected</span>
                ) : (
                  <button
                    onClick={() => handleDeleteEdge(conn.edgeId, conn.relationship)}
                    className="text-red-400 hover:text-red-600 text-[10px] px-1"
                    title="Delete edge"
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export const NodeDetailsSidebar = memo(NodeDetailsSidebarInner);
