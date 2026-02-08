import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function CountryNodeComponent({ data }: NodeProps) {
  return (
    <div className="px-2 py-1 rounded-md border border-blue-300 bg-blue-50 text-xs shadow-sm min-w-[80px]">
      <Handle type="target" position={Position.Left} className="!bg-blue-400" />
      <div className="text-blue-900 font-medium">{String(data.label || '')}</div>
      <Handle type="source" position={Position.Right} className="!bg-blue-400" />
    </div>
  );
}

export const CountryNode = memo(CountryNodeComponent);
