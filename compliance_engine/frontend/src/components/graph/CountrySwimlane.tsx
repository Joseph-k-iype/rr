import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';

function CountrySwimlaneComponent({ data }: NodeProps) {
  return (
    <div className="bg-blue-50 border-2 border-blue-200 rounded-xl px-4 py-3 min-w-[200px] shadow">
      <div className="text-sm font-bold text-blue-900">{String(data.label || '')}</div>
      <div className="text-[10px] text-blue-600 mt-1">
        {String(data.country_count || 0)} countries
      </div>
      <div className="text-[9px] text-gray-500 mt-1 max-h-12 overflow-hidden">
        {(data.countries as string[] || []).slice(0, 5).join(', ')}
        {(data.countries as string[] || []).length > 5 ? '...' : ''}
      </div>
    </div>
  );
}

export const CountrySwimlane = memo(CountrySwimlaneComponent);
