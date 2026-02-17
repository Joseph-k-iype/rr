import { ReactFlowProvider } from '@xyflow/react';
import { useEditorData } from '../hooks/useEditorData';
import { useEditorStore } from '../stores/editorStore';
import { PolicyEditorCanvas } from '../components/editor/PolicyEditorCanvas';
import { NodeDetailsSidebar } from '../components/editor/NodeDetailsSidebar';

export function EditorPage() {
  const { isLoading, error } = useEditorData();
  const sidebarNodeId = useEditorStore((s) => s.sidebarNodeId);

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col">
      <div className="px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-800">Policy Editor</h1>
      </div>

      {error && (
        <div className="mx-6 mb-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Failed to load graph data: {error.message}
        </div>
      )}

      <div className="flex-1 mx-4 mb-4 border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm flex">
        {isLoading ? (
          <div className="flex items-center justify-center h-full flex-1">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-500">Loading policy graph...</span>
            </div>
          </div>
        ) : (
          <ReactFlowProvider>
            <div className="flex-1 flex">
              <div className="flex-1 overflow-hidden">
                <PolicyEditorCanvas />
              </div>
              {sidebarNodeId && <NodeDetailsSidebar />}
            </div>
          </ReactFlowProvider>
        )}
      </div>
    </div>
  );
}
