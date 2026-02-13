import { useEvaluationStore } from '../../stores/evaluationStore';

export function EvaluationResult() {
  const { result } = useEvaluationStore();

  if (!result) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 text-sm">
        Run an evaluation to see results
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      {/* Triggered Rules */}
      {result.triggered_rules.map((rule, i) => (
        <div key={`${rule.rule_id}-${i}`} className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-start justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Rule {i + 1}</span>
            <span className={rule.outcome === 'permission' ? 'badge-permission text-sm' : 'badge-prohibition text-sm'}>
              {rule.outcome === 'permission' ? 'Permission' : 'Prohibition'}
            </span>
          </div>
          <p className="text-sm text-gray-800 font-medium mb-2">{rule.rule_name}</p>
          {rule.description && <p className="text-xs text-gray-500 mb-2">{rule.description}</p>}

          {/* Duties for permissions */}
          {rule.outcome === 'permission' && rule.permissions?.map(p =>
            p.duties?.map(d => (
              <div key={d.duty_id} className="mt-1">
                <span className="text-xs font-semibold text-blue-600">Duty</span>
                <p className="text-xs text-gray-700">{d.name}</p>
              </div>
            ))
          )}
        </div>
      ))}

      {/* Precedent Cases */}
      {result.precedent_validation && result.precedent_validation.matching_cases.length > 0 && (
        <div className="border-t pt-3">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>List of cases matched</span>
            <span>{result.precedent_validation.matching_cases.map(c => c.case_ref_id).join(', ')}</span>
          </div>
        </div>
      )}

      {/* Overall Result */}
      <div className="border-t pt-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold text-gray-900">Evaluation Result</span>
          <span className={`text-sm font-bold ${
            result.transfer_status === 'ALLOWED' ? 'text-green-600' :
            result.transfer_status === 'PROHIBITED' ? 'text-red-600' :
            'text-yellow-600'
          }`}>
            {result.transfer_status === 'ALLOWED' ? 'Permission' :
             result.transfer_status === 'PROHIBITED' ? 'Prohibition' :
             result.transfer_status}
          </span>
        </div>
      </div>

      {result.prohibition_reasons.length > 0 && (
        <div className="text-xs text-red-600">
          {result.prohibition_reasons.map((r, i) => <p key={i}>{r}</p>)}
        </div>
      )}
    </div>
  );
}
