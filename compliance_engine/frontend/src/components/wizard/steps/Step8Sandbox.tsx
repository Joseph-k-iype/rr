import { useWizardStore } from '../../../stores/wizardStore';
import { LoadingSpinner } from '../../common/LoadingSpinner';

export function Step8Sandbox() {
  const { sandboxGraphName, editedRuleDefinition, isProcessing, error } = useWizardStore();

  if (isProcessing) return <LoadingSpinner message="Loading rule into sandbox..." />;

  const rule = editedRuleDefinition as Record<string, unknown> | null;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Load to Sandbox</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 font-medium">Sandbox Error</p>
          <p className="text-xs text-red-600 mt-1">{error}</p>
          <p className="text-xs text-gray-500 mt-2">You can go Back to fix the rule definition and try again.</p>
        </div>
      )}

      {sandboxGraphName ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2.5 h-2.5 bg-green-500 rounded-full" />
            <span className="text-sm font-medium text-green-800">Sandbox Ready</span>
          </div>
          <p className="text-sm text-green-700">
            Rule loaded into sandbox graph: <code className="bg-green-100 px-1.5 py-0.5 rounded text-xs font-mono">{sandboxGraphName}</code>
          </p>
          <p className="text-xs text-green-600 mt-2">Click Next to test the rule in the sandbox.</p>
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-5">
          <p className="text-sm text-blue-800 font-medium">Ready to Load</p>
          <p className="text-sm text-blue-700 mt-1">
            Your rule will be loaded into a temporary sandbox graph for safe testing. The main graph will not be affected.
          </p>

          {rule && (
            <div className="mt-4 bg-white rounded-lg border border-blue-100 p-3">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <div>
                  <span className="text-gray-500">Rule ID:</span>{' '}
                  <span className="font-mono text-gray-800">{rule.rule_id as string}</span>
                </div>
                <div>
                  <span className="text-gray-500">Type:</span>{' '}
                  <span className="text-gray-800">{rule.rule_type as string}</span>
                </div>
                <div>
                  <span className="text-gray-500">Outcome:</span>{' '}
                  <span className={`font-medium ${rule.outcome === 'prohibition' ? 'text-red-700' : 'text-green-700'}`}>
                    {rule.outcome as string}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Priority:</span>{' '}
                  <span className="text-gray-800">{String(rule.priority)}</span>
                </div>
              </div>
            </div>
          )}

          <p className="text-xs text-blue-600 mt-3">Click Next to create the sandbox and load the rule.</p>
        </div>
      )}
    </div>
  );
}
