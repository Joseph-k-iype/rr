import { useWizardStore } from '../../../stores/wizardStore';
import { LoadingSpinner } from '../../common/LoadingSpinner';
import { StatusBadge } from '../../common/StatusBadge';

export function Step4Analysis() {
  const { analysisResult, isProcessing, error } = useWizardStore();

  if (isProcessing) return <LoadingSpinner message="AI agents analyzing rule..." />;
  if (error) return <div className="text-red-600 text-sm p-4 bg-red-50 rounded-lg">{error}</div>;

  if (!analysisResult) {
    return <p className="text-sm text-gray-500">No analysis result yet. Go back and submit the rule text.</p>;
  }

  const result = analysisResult as Record<string, unknown>;
  const ruleType = (result.rule_type as string) || (result.scenario_type as string) || 'Unknown';
  const confidence = result.confidence_score as number | undefined;
  const summary = (result.summary as string) || (result.analysis as string) || '';
  const countries = result.countries_identified as string[] | undefined;
  const originCountry = result.origin_country as string | undefined;
  const receivingCountries = result.receiving_countries as string[] | undefined;
  const attributes = result.detected_attributes as string[] | undefined;
  const warnings = result.warnings as string[] | undefined;
  const actions = result.suggested_actions as string[] | undefined;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">AI Analysis Complete</h3>

      {/* Summary Card */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-blue-900">Analysis Summary</span>
          <div className="flex items-center gap-2">
            <StatusBadge status={ruleType} />
            {confidence !== undefined && (
              <span className="text-xs text-blue-600 font-medium">
                {Math.round(confidence * 100)}% confidence
              </span>
            )}
          </div>
        </div>
        {summary && <p className="text-sm text-blue-800">{summary}</p>}
      </div>

      {/* Countries */}
      {(originCountry || (receivingCountries && receivingCountries.length > 0) || (countries && countries.length > 0)) && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Countries Identified</h4>
          <div className="grid grid-cols-2 gap-4">
            {originCountry && (
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Origin</span>
                <p className="text-sm font-medium text-gray-800 mt-0.5">{originCountry}</p>
              </div>
            )}
            {receivingCountries && receivingCountries.length > 0 && (
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Receiving</span>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {receivingCountries.map(c => (
                    <span key={c} className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">{c}</span>
                  ))}
                </div>
              </div>
            )}
            {countries && countries.length > 0 && !originCountry && (
              <div className="col-span-2">
                <span className="text-xs text-gray-500 uppercase tracking-wide">Countries</span>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {countries.map(c => (
                    <span key={c} className="inline-flex items-center px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">{c}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detected Attributes */}
      {attributes && attributes.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-gray-900 mb-2">Detected Attributes</h4>
          <div className="flex flex-wrap gap-1.5">
            {attributes.map(attr => (
              <span key={attr} className="inline-flex items-center px-2.5 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-full text-xs">{attr}</span>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings && warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-yellow-800 mb-2">Warnings</h4>
          <ul className="space-y-1">
            {warnings.map((w, i) => (
              <li key={i} className="text-xs text-yellow-700 flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0">!</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggested Actions */}
      {actions && actions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-gray-900 mb-2">Suggested Actions</h4>
          <ul className="space-y-1">
            {actions.map((a, i) => (
              <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                <span className="text-blue-500 mt-0.5 shrink-0">&#10003;</span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Raw Data (collapsible) */}
      <details className="text-xs">
        <summary className="text-gray-400 cursor-pointer hover:text-gray-600">View raw analysis data</summary>
        <pre className="bg-gray-50 p-3 rounded-lg mt-2 overflow-auto max-h-48 border border-gray-200 text-gray-600">
          {JSON.stringify(analysisResult, null, 2)}
        </pre>
      </details>
    </div>
  );
}
