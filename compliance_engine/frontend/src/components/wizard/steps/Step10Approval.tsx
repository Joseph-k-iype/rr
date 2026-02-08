import { useWizardStore } from '../../../stores/wizardStore';
import { StatusBadge } from '../../common/StatusBadge';

export function Step10Approval() {
  const { editedRuleDefinition, sandboxTestResults, approved } = useWizardStore();
  const rule = editedRuleDefinition as Record<string, unknown> | null;

  if (approved) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Rule Approved</h3>
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="text-green-600 text-xl">&#10003;</span>
          </div>
          <p className="text-lg text-green-800 font-semibold">Rule Approved & Loaded</p>
          <p className="text-sm text-green-700 mt-2">
            Rule <span className="font-mono bg-green-100 px-1.5 rounded">{(rule?.rule_id as string) || ''}</span> has been loaded into the main rules graph and is now active.
          </p>
        </div>
      </div>
    );
  }

  // Count test results by status
  const testsByStatus: Record<string, number> = {};
  sandboxTestResults.forEach(r => {
    const status = (r.transfer_status as string) || 'UNKNOWN';
    testsByStatus[status] = (testsByStatus[status] || 0) + 1;
  });

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Final Approval</h3>

      {/* Rule Summary Card */}
      {rule && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-gray-500 font-mono">{rule.rule_id as string}</span>
                <h4 className="text-sm font-semibold text-gray-900">{rule.name as string}</h4>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={(rule.outcome as string) || ''} />
                <StatusBadge status={(rule.rule_type as string) || ''} />
              </div>
            </div>
          </div>
          <div className="p-4">
            <p className="text-sm text-gray-700 mb-3">{rule.description as string}</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-gray-500">Priority:</span>{' '}
                <span className="font-medium">{String(rule.priority)}</span>
              </div>
              <div>
                <span className="text-gray-500">ODRL Type:</span>{' '}
                <span className="font-medium">{rule.odrl_type as string}</span>
              </div>
              <div>
                <span className="text-gray-500">Origin:</span>{' '}
                <span className="font-medium">{(rule.origin_group as string) || (rule.origin_countries as string[])?.join(', ') || 'Any'}</span>
              </div>
              <div>
                <span className="text-gray-500">Receiving:</span>{' '}
                <span className="font-medium">{(rule.receiving_group as string) || (rule.receiving_countries as string[])?.join(', ') || 'Any'}</span>
              </div>
              <div>
                <span className="text-gray-500">PII Required:</span>{' '}
                <span className="font-medium">{rule.requires_pii ? 'Yes' : 'No'}</span>
              </div>
              {rule.attribute_name && (
                <div>
                  <span className="text-gray-500">Attribute:</span>{' '}
                  <span className="font-medium">{rule.attribute_name as string}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Test Summary */}
      <div className="border border-gray-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-900 mb-2">Test Summary</h4>
        {sandboxTestResults.length === 0 ? (
          <p className="text-xs text-gray-500">No sandbox tests were run. Consider going back to test first.</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            <div className="text-center px-3 py-2 bg-gray-50 rounded-lg">
              <p className="text-lg font-bold text-gray-800">{sandboxTestResults.length}</p>
              <p className="text-[10px] text-gray-500 uppercase">Total Tests</p>
            </div>
            {Object.entries(testsByStatus).map(([status, count]) => (
              <div key={status} className={`text-center px-3 py-2 rounded-lg ${
                status === 'ALLOWED' ? 'bg-green-50' :
                status === 'PROHIBITED' ? 'bg-red-50' :
                'bg-yellow-50'
              }`}>
                <p className={`text-lg font-bold ${
                  status === 'ALLOWED' ? 'text-green-700' :
                  status === 'PROHIBITED' ? 'text-red-700' :
                  'text-yellow-700'
                }`}>{count}</p>
                <p className="text-[10px] text-gray-500 uppercase">{status}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Warning */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-sm text-yellow-800 font-medium">Confirm Approval</p>
        <p className="text-xs text-yellow-700 mt-1">
          Clicking "Approve & Load" will add this rule to the main rules graph. It will immediately take effect for all evaluations.
        </p>
      </div>
    </div>
  );
}
