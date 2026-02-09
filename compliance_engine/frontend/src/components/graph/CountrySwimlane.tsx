import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function CountrySwimlaneComponent({ data }: NodeProps) {
  const expanded = data.expanded as boolean;
  const countries = (data.countries as string[]) || [];
  const countryCount = (data.country_count as number) || countries.length;

  return (
    <div
      onClick={() => (data.onExpand as (() => void) | undefined)?.()}
      className="bg-white border border-gray-200 rounded min-w-[160px] cursor-pointer select-none"
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />

      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-medium text-gray-900 tracking-tight">{String(data.label || '')}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-400 tabular-nums">{countryCount}</span>
          <span className="text-[9px] text-gray-300">{expanded ? '\u25B4' : '\u25BE'}</span>
        </div>
      </div>

      {expanded && countries.length > 0 && (
        <div className="border-t border-gray-100 px-3 py-1.5">
          {countries.map(c => (
            <div key={c} className="text-[11px] text-gray-500 py-0.5">{c}</div>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
    </div>
  );
}

export const CountrySwimlane = memo(CountrySwimlaneComponent);
