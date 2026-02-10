import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function AdminSwimlaneComponent({ data }: NodeProps) {
  return (
    <div className="px-2 py-1.5 rounded border border-gray-200 bg-white text-xs min-w-[120px]">
      <Handle type="target" position={Position.Left} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
      <div className="font-medium text-gray-900 truncate">{String(data.label || '')}</div>
      {data.category && (
        <div className="text-gray-400 text-[9px] truncate">{String(data.category)}</div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
    </div>
  );
}

export const AdminSwimlane = memo(AdminSwimlaneComponent);
