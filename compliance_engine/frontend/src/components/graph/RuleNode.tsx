import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

function RuleNodeComponent({ data }: NodeProps) {
  const isProhibition = data.outcome === 'prohibition' || data.odrl_type === 'Prohibition';
  const borderColor = isProhibition ? 'border-red-400' : 'border-green-400';
  const typeBadgeColor = isProhibition ? 'text-red-600' : 'text-green-600';
  const typeLabel = isProhibition ? 'Prohibition' : 'Permission';
  const ruleName = isProhibition
    ? String(data.prohibition_name || data.rule_id || 'Rule')
    : String(data.permission_name || data.rule_id || 'Rule');
  const actionText = isProhibition ? 'Consult Legal' : 'Allowed';

  return (
    <div className={`bg-white border-2 ${borderColor} rounded-lg min-w-[200px] max-w-[260px] shadow-sm`}>
      <Handle type="target" position={Position.Left} className="!bg-gray-400 !w-2 !h-2" />

      {/* Header row */}
      <div className="flex items-start justify-between px-3 pt-2 pb-1">
        <span className="text-sm font-bold text-gray-900">{ruleName}</span>
        <span className={`text-xs font-bold ${typeBadgeColor} ml-2 whitespace-nowrap`}>{typeLabel}</span>
      </div>

      {/* Description */}
      <div className="px-3 pb-1.5">
        <p className="text-[10px] text-gray-500 leading-tight">
          P{String(data.priority || 0)} {data.has_pii_required ? '| PII Required' : ''}
        </p>
      </div>

      {/* Action */}
      <div className="px-3 pb-2 border-t border-gray-100 pt-1.5">
        <span className={`text-[10px] font-semibold ${typeBadgeColor}`}>Action</span>
        <div className={`text-xs font-medium ${typeBadgeColor}`}>{actionText}</div>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-gray-400 !w-2 !h-2" />
    </div>
  );
}

export const RuleNode = memo(RuleNodeComponent);
