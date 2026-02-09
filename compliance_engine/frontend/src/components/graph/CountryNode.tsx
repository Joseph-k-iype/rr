import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function CountryNodeComponent({ data }: NodeProps) {
  return (
    <div className="bg-white border border-gray-200 rounded px-3 py-1.5 min-w-[100px]">
      <Handle type="target" position={Position.Left} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
      <span className="text-[11px] text-gray-700">{String(data.label || '')}</span>
      <Handle type="source" position={Position.Right} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
    </div>
  );
}

export const CountryNode = memo(CountryNodeComponent);
