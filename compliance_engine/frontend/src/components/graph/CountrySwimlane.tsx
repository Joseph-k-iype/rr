import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function CountrySwimlaneComponent({ data }: NodeProps) {
  const expanded = data.expanded as boolean;
  const countries = (data.countries as string[]) || [];
  const countryCount = data.country_count as number || countries.length;

  return (
    <div
      onClick={() => (data.onExpand as (() => void) | undefined)?.()}
      className="bg-white border border-gray-300 rounded-lg min-w-[180px] shadow-sm cursor-pointer select-none"
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400 !w-2 !h-2" />

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">{expanded ? '\u25BC' : '\u25B6'}</span>
          <span className="text-sm font-semibold text-gray-800">{String(data.label || '')}</span>
        </div>
        <span className="text-xs text-gray-400 font-medium">{countryCount}</span>
      </div>

      {/* Country list (visible when expanded) */}
      {expanded && countries.length > 0 && (
        <div className="px-3 py-1.5 space-y-0.5">
          {countries.map(c => (
            <div key={c} className="flex items-center justify-between text-xs text-gray-600 py-0.5">
              <span className="flex items-center gap-1">
                <span className="text-gray-400">{'\u25B6'}</span>
                {c}
              </span>
            </div>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-gray-400 !w-2 !h-2" />
    </div>
  );
}

export const CountrySwimlane = memo(CountrySwimlaneComponent);
