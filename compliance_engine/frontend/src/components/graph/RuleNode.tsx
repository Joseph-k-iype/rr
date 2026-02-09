import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function RuleNodeComponent({ data }: NodeProps) {
  const isProhibition = data.outcome === 'prohibition' || data.odrl_type === 'Prohibition';
  const accentColor = isProhibition ? 'bg-red-500' : 'bg-green-500';
  const ruleName = isProhibition
    ? String(data.prohibition_name || data.rule_id || 'Rule')
    : String(data.permission_name || data.rule_id || 'Rule');

  return (
    <div className="bg-white border border-gray-200 rounded min-w-[180px] max-w-[220px]">
      <Handle type="target" position={Position.Left} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />

      {/* Accent bar */}
      <div className={`h-0.5 ${accentColor}`} />

      <div className="px-3 py-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-900 truncate">{ruleName}</span>
          <span className={`text-[9px] uppercase tracking-wider font-medium ${isProhibition ? 'text-red-500' : 'text-green-600'}`}>
            {isProhibition ? 'Prohib' : 'Perm'}
          </span>
        </div>
        <div className="text-[10px] text-gray-400 tabular-nums">
          P{String(data.priority || 0)}{data.has_pii_required ? ' \u00B7 PII' : ''}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-gray-300 !w-1.5 !h-1.5 !border-0" />
    </div>
  );
}

export const RuleNode = memo(RuleNodeComponent);
