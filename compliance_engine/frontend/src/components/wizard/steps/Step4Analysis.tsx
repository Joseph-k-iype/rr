import { useWizardStore } from '../../../stores/wizardStore';
import { LoadingSpinner } from '../../common/LoadingSpinner';

export function Step4Analysis() {
  const { analysisResult, isProcessing, error } = useWizardStore();

  if (isProcessing) return <LoadingSpinner message="AI agents analyzing rule..." />;
  if (error) return <div className="text-red-600 text-sm p-4 bg-red-50 rounded-lg">{error}</div>;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 4: AI Analysis Result</h3>
      {analysisResult ? (
        <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-96 border border-gray-200">
          {JSON.stringify(analysisResult, null, 2)}
        </pre>
      ) : (
        <p className="text-sm text-gray-500">No analysis result yet. Go back and submit the rule text.</p>
      )}
    </div>
  );
}
