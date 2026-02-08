import { useWizardStore } from '../../../stores/wizardStore';

export function Step10Approval() {
  const { editedRuleDefinition, sandboxTestResults, approved } = useWizardStore();

  if (approved) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Step 10: Final Approval</h3>
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <p className="text-lg text-green-800 font-semibold">Rule Approved Successfully</p>
          <p className="text-sm text-green-700 mt-2">
            Rule <span className="font-mono">{editedRuleDefinition?.rule_id as string || ''}</span> has been loaded into the main graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 10: Final Approval</h3>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-sm text-yellow-800 font-medium">Review Summary</p>
        <ul className="text-xs text-yellow-700 mt-2 space-y-1">
          <li>Rule ID: {editedRuleDefinition?.rule_id as string || 'N/A'}</li>
          <li>Rule Type: {editedRuleDefinition?.rule_type as string || 'N/A'}</li>
          <li>Sandbox Tests Run: {sandboxTestResults.length}</li>
        </ul>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          Click "Approve &amp; Load" to load this rule into the main graph. This action cannot be undone.
        </p>
      </div>

      <div>
        <h4 className="text-sm font-medium text-gray-900 mb-2">Final Rule Definition</h4>
        <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-48 border border-gray-200">
          {editedRuleDefinition ? JSON.stringify(editedRuleDefinition, null, 2) : 'No rule'}
        </pre>
      </div>
    </div>
  );
}
