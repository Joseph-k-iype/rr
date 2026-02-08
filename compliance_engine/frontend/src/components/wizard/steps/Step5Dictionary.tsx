import { useWizardStore } from '../../../stores/wizardStore';

export function Step5Dictionary() {
  const { dictionaryResult } = useWizardStore();

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 5: Generated Dictionary</h3>
      {dictionaryResult ? (
        <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-96 border border-gray-200">
          {JSON.stringify(dictionaryResult, null, 2)}
        </pre>
      ) : (
        <p className="text-sm text-gray-500">No dictionary generated (may not be needed for transfer rules).</p>
      )}
    </div>
  );
}
