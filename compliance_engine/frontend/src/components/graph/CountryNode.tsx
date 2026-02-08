import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function CountryNodeComponent({ data }: NodeProps) {
  const isOrigin = data.side === 'origin';
  const borderColor = isOrigin ? 'border-amber-400 bg-amber-50' : 'border-red-300 bg-red-50';
  const textColor = isOrigin ? 'text-amber-900' : 'text-red-900';

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-md border-2 ${borderColor} shadow-sm min-w-[140px]`}>
      <Handle type="target" position={Position.Left} className="!bg-gray-400 !w-2 !h-2" />
      <span className="text-xs text-gray-400">{'\u25B6'}</span>
      <span className={`text-xs font-medium ${textColor} flex-1`}>{String(data.label || '')}</span>
      <Handle type="source" position={Position.Right} className="!bg-gray-400 !w-2 !h-2" />
    </div>
  );
}

export const CountryNode = memo(CountryNodeComponent);
