import { useState } from 'react';
import { WizardContainer } from '../components/wizard/WizardContainer';
import { useWizardStore } from '../stores/wizardStore';
import { cancelWizard } from '../services/wizardApi';

export function WizardPage() {
  const { sessionId, currentStep, reset } = useWizardStore();
  const [confirming, setConfirming] = useState(false);

  const handleReset = async () => {
    if (currentStep > 1 && !confirming) {
      setConfirming(true);
      return;
    }
    // Cancel backend session to clean up sandbox graphs
    if (sessionId) {
      try { await cancelWizard(sessionId); } catch { /* ignore cleanup errors */ }
    }
    reset();
    setConfirming(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Rule Ingestion Wizard</h1>
        <div className="flex items-center gap-2">
          {confirming && (
            <span className="text-xs text-amber-600">Are you sure? Progress will be lost.</span>
          )}
          <button
            onClick={handleReset}
            className={`text-sm border px-3 py-1 rounded-md ${confirming ? 'text-red-600 border-red-300 hover:bg-red-50' : 'text-gray-500 hover:text-gray-700 border-gray-300'}`}
          >
            {confirming ? 'Confirm Reset' : 'Start Over'}
          </button>
          {confirming && (
            <button onClick={() => setConfirming(false)} className="text-xs text-gray-400 hover:text-gray-600">
              Cancel
            </button>
          )}
        </div>
      </div>
      <WizardContainer />
    </div>
  );
}
