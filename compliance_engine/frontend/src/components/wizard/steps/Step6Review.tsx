import { useWizardStore } from '../../../stores/wizardStore';
import { StatusBadge } from '../../common/StatusBadge';

function RuleCard({ rule }: { rule: Record<string, unknown> }) {
  const ruleId = (rule.rule_id as string) || '';
  const name = (rule.name as string) || '';
  const description = (rule.description as string) || '';
  const ruleType = (rule.rule_type as string) || '';
  const outcome = (rule.outcome as string) || '';
  const priority = rule.priority as number | undefined;
  const odrlType = (rule.odrl_type as string) || '';
  const originGroup = (rule.origin_group as string) || '';
  const receivingGroup = (rule.receiving_group as string) || '';
  const originCountries = rule.origin_countries as string[] | undefined;
  const receivingCountries = rule.receiving_countries as string[] | undefined;
  const requiresPii = rule.requires_pii as boolean | undefined;
  const attributeName = rule.attribute_name as string | undefined;
  const attributeKeywords = rule.attribute_keywords as string[] | undefined;
  const requiredActions = rule.required_actions as string[] | undefined;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs text-gray-500 font-mono">{ruleId}</span>
            <h4 className="text-sm font-semibold text-gray-900">{name}</h4>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={outcome} />
            <StatusBadge status={ruleType} />
            {priority !== undefined && (
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">P{priority}</span>
            )}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {description && <p className="text-sm text-gray-700">{description}</p>}

        <div className="grid grid-cols-2 gap-4">
          {/* Origin */}
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide">Origin</span>
            {originGroup ? (
              <p className="text-sm text-gray-800 mt-0.5">{originGroup}</p>
            ) : originCountries && originCountries.length > 0 ? (
              <div className="flex flex-wrap gap-1 mt-0.5">
                {originCountries.map(c => (
                  <span key={c} className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded">{c}</span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 mt-0.5">Any</p>
            )}
          </div>

          {/* Receiving */}
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide">Receiving</span>
            {receivingGroup ? (
              <p className="text-sm text-gray-800 mt-0.5">{receivingGroup}</p>
            ) : receivingCountries && receivingCountries.length > 0 ? (
              <div className="flex flex-wrap gap-1 mt-0.5">
                {receivingCountries.map(c => (
                  <span key={c} className="text-xs bg-red-50 text-red-700 border border-red-200 px-1.5 py-0.5 rounded">{c}</span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 mt-0.5">Any</p>
            )}
          </div>
        </div>

        {/* Additional details row */}
        <div className="flex flex-wrap gap-3 text-xs text-gray-600">
          {odrlType && (
            <span>ODRL: <span className="font-medium">{odrlType}</span></span>
          )}
          {requiresPii !== undefined && (
            <span>PII Required: <span className="font-medium">{requiresPii ? 'Yes' : 'No'}</span></span>
          )}
          {attributeName && (
            <span>Attribute: <span className="font-medium">{attributeName}</span></span>
          )}
        </div>

        {/* Attribute keywords */}
        {attributeKeywords && attributeKeywords.length > 0 && (
          <div>
            <span className="text-xs text-gray-500">Keywords</span>
            <div className="flex flex-wrap gap-1 mt-0.5">
              {attributeKeywords.map(kw => (
                <span key={kw} className="text-xs bg-purple-50 text-purple-700 border border-purple-200 px-1.5 py-0.5 rounded">{kw}</span>
              ))}
            </div>
          </div>
        )}

        {/* Required actions */}
        {requiredActions && requiredActions.length > 0 && (
          <div>
            <span className="text-xs text-gray-500">Required Actions</span>
            <ul className="mt-0.5 space-y-0.5">
              {requiredActions.map((a, i) => (
                <li key={i} className="text-xs text-gray-700 flex items-center gap-1">
                  <span className="text-blue-500">&#8226;</span> {a}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function Step6Review() {
  const { editedRuleDefinition, dictionaryResult } = useWizardStore();

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Review Generated Content</h3>
      <p className="text-sm text-gray-600">Review the AI-generated rule definition before proceeding to edit.</p>

      {/* Rule Definition */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-2">Rule Definition</h4>
        {editedRuleDefinition ? (
          <RuleCard rule={editedRuleDefinition} />
        ) : (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
            No rule definition generated. Go back and resubmit.
          </div>
        )}
      </div>

      {/* Dictionary Summary */}
      {dictionaryResult && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Terms Dictionary</h4>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            {(() => {
              const dict = dictionaryResult as Record<string, unknown>;
              const terms = dict.terms as Record<string, unknown>[] | undefined;
              const count = terms ? terms.length : Object.keys(dict).length;
              return (
                <p className="text-sm text-gray-700">
                  {count} term{count !== 1 ? 's' : ''} identified
                </p>
              );
            })()}
          </div>
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-xs text-blue-700">Click Next to proceed to editing, or Back to regenerate.</p>
      </div>
    </div>
  );
}
