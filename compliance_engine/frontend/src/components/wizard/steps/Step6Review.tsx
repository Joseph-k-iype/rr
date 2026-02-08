import { useWizardStore } from '../../../stores/wizardStore';

export function Step6Review() {
  const { editedRuleDefinition, dictionaryResult } = useWizardStore();

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 6: Review Generated Content</h3>
      <p className="text-sm text-gray-600">Review the generated rule definition and dictionary before editing.</p>

      <div>
        <h4 className="text-sm font-medium text-gray-900 mb-2">Rule Definition</h4>
        <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-64 border border-gray-200">
          {editedRuleDefinition ? JSON.stringify(editedRuleDefinition, null, 2) : 'No rule definition generated'}
        </pre>
      </div>

      {dictionaryResult && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">Terms Dictionary</h4>
          <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-64 border border-gray-200">
            {JSON.stringify(dictionaryResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
