import { useWizardStore } from '../../../stores/wizardStore';
import { LoadingSpinner } from '../../common/LoadingSpinner';

export function Step8Sandbox() {
  const { sandboxGraphName, isProcessing } = useWizardStore();

  if (isProcessing) return <LoadingSpinner message="Loading rule into sandbox..." />;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 8: Load to Sandbox</h3>
      {sandboxGraphName ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm text-green-800">Rule loaded into sandbox graph: <code className="bg-green-100 px-1 rounded">{sandboxGraphName}</code></p>
          <p className="text-xs text-green-600 mt-1">You can now test the rule in the next step.</p>
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">Click "Next" to load the rule into a temporary sandbox graph for testing.</p>
        </div>
      )}
    </div>
  );
}
