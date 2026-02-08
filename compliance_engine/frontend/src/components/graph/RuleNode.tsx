import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function RuleNodeComponent({ data }: NodeProps) {
  const isProhibition = data.outcome === 'prohibition' || data.odrl_type === 'Prohibition';
  const bgColor = isProhibition ? 'bg-red-50 border-red-300' : 'bg-green-50 border-green-300';
  const textColor = isProhibition ? 'text-red-800' : 'text-green-800';

  return (
    <div className={`px-3 py-2 rounded-lg border-2 shadow-sm min-w-[140px] ${bgColor}`}>
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <div className={`text-xs font-bold ${textColor}`}>{String(data.rule_id || '')}</div>
      <div className="text-[10px] text-gray-600 mt-0.5">
        P{String(data.priority || 0)} {data.has_pii_required ? '| PII' : ''}
      </div>
      <div className={`text-[10px] mt-0.5 font-medium ${textColor}`}>
        {isProhibition ? String(data.prohibition_name || 'Prohibition') : String(data.permission_name || 'Permission')}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
    </div>
  );
}

export const RuleNode = memo(RuleNodeComponent);
