import { useEvaluationStore } from '../../stores/evaluationStore';
import { StatusBadge } from '../common/StatusBadge';

export function EvaluationResult() {
  const { result } = useEvaluationStore();

  if (!result) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Evaluation Result</h3>
        <StatusBadge status={result.transfer_status} />
      </div>

      <div className="text-sm text-gray-600">
        <p>{result.message}</p>
        <p className="text-xs text-gray-400 mt-1">Evaluated in {result.evaluation_time_ms.toFixed(0)}ms</p>
      </div>

      {result.triggered_rules.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">Triggered Rules</h4>
          <div className="space-y-2">
            {result.triggered_rules.map(rule => (
              <div key={rule.rule_id} className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm">
                <div>
                  <span className="font-medium">{rule.rule_name}</span>
                  <span className="text-xs text-gray-500 ml-2">({rule.rule_type})</span>
                </div>
                <StatusBadge status={rule.outcome} />
              </div>
            ))}
          </div>
        </div>
      )}

      {result.precedent_validation && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">Precedent Cases</h4>
          <div className="text-sm text-gray-600">
            <p>Found: {result.precedent_validation.total_matches} | Compliant: {result.precedent_validation.compliant_matches}</p>
          </div>
          {result.precedent_validation.matching_cases.slice(0, 5).map(c => (
            <div key={c.case_id} className="flex items-center justify-between p-2 bg-gray-50 rounded text-xs mt-1">
              <span>{c.case_ref_id}</span>
              <span className="text-gray-500">Score: {(c.match_score * 100).toFixed(0)}%</span>
              <StatusBadge status={c.is_compliant ? 'ALLOWED' : 'REQUIRES_REVIEW'} />
            </div>
          ))}
        </div>
      )}

      {result.detected_attributes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">Detected Attributes</h4>
          <div className="flex flex-wrap gap-1">
            {result.detected_attributes.map(attr => (
              <span key={attr.attribute_name} className="bg-purple-50 text-purple-700 text-xs px-2 py-0.5 rounded-full border border-purple-200">
                {attr.attribute_name} ({(attr.confidence * 100).toFixed(0)}%)
              </span>
            ))}
          </div>
        </div>
      )}

      {result.prohibition_reasons.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-red-800 mb-2">Prohibition Reasons</h4>
          <ul className="list-disc list-inside text-sm text-red-600">
            {result.prohibition_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
