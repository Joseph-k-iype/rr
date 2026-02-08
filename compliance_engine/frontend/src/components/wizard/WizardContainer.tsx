import { useCallback } from 'react';
import { useWizardStore } from '../../stores/wizardStore';
import { useAgentEvents } from '../../hooks/useAgentEvents';
import { startWizardSession, submitWizardStep, getWizardSession, loadSandbox, approveWizard } from '../../services/wizardApi';
import { WizardStepper } from './WizardStepper';
import { WizardNavigation } from './WizardNavigation';
import { AgentProgressPanel } from './shared/AgentProgressPanel';
import { Step1Country } from './steps/Step1Country';
import { Step2Scenario } from './steps/Step2Scenario';
import { Step3RuleText } from './steps/Step3RuleText';
import { Step4Analysis } from './steps/Step4Analysis';
import { Step5Dictionary } from './steps/Step5Dictionary';
import { Step6Review } from './steps/Step6Review';
import { Step7Edit } from './steps/Step7Edit';
import { Step8Sandbox } from './steps/Step8Sandbox';
import { Step9Test } from './steps/Step9Test';
import { Step10Approval } from './steps/Step10Approval';

const stepComponents: Record<number, React.FC> = {
  1: Step1Country,
  2: Step2Scenario,
  3: Step3RuleText,
  4: Step4Analysis,
  5: Step5Dictionary,
  6: Step6Review,
  7: Step7Edit,
  8: Step8Sandbox,
  9: Step9Test,
  10: Step10Approval,
};

export function WizardContainer() {
  const store = useWizardStore();
  const { events, connected } = useAgentEvents(store.sessionId);

  const canGoNext = useCallback(() => {
    switch (store.currentStep) {
      case 1: return !!store.originCountry;
      case 2: return !!store.scenarioType && (
        store.scenarioType !== 'transfer' || store.receivingCountries.length > 0
      ) && (
        store.scenarioType !== 'attribute' || store.dataCategories.length > 0
      );
      case 3: return store.ruleText.length > 10;
      case 4: return !!store.analysisResult;
      case 5: return true;
      case 6: return !!store.editedRuleDefinition;
      case 7: return !!store.editedRuleDefinition;
      case 8: return !!store.sandboxGraphName;
      case 9: return store.sandboxTestResults.length > 0;
      case 10: return true;
      default: return false;
    }
  }, [store]);

  const handleNext = async () => {
    // Read fresh state directly from Zustand to avoid stale closures
    const state = useWizardStore.getState();
    const step = state.currentStep;
    let sessionId = state.sessionId;

    store.setError(null);
    store.setProcessing(true);

    try {
      // Step 1: create session if needed
      if (step === 1 && !sessionId) {
        const { session_id } = await startWizardSession();
        store.setSessionId(session_id);
        sessionId = session_id;
      }

      // Steps 1-3: submit step data to backend
      if (step <= 3 && sessionId) {
        const stepData: Record<number, Record<string, unknown>> = {
          1: { origin_country: state.originCountry, receiving_countries: state.receivingCountries },
          2: { scenario_type: state.scenarioType, data_categories: state.dataCategories },
          3: { rule_text: state.ruleText },
        };

        const result = await submitWizardStep(sessionId, { step, data: stepData[step] || {} });

        if (step === 3) {
          if (result.status === 'failed') {
            store.setError(result.error_message || 'AI processing failed');
            store.setProcessing(false);
            return;
          } else {
            const session = await getWizardSession(sessionId);
            if (session.analysis_result) {
              store.setAnalysisResult(session.analysis_result);
            }
            if (session.dictionary_result) {
              store.setDictionaryResult(session.dictionary_result);
            }
            if (session.edited_rule_definition) {
              store.setEditedRuleDefinition(session.edited_rule_definition);
            }
            if (session.edited_terms_dictionary) {
              store.setEditedTermsDictionary(session.edited_terms_dictionary);
            }
          }
        }
      }

      // Step 8: load sandbox
      if (step === 8 && sessionId && !state.sandboxGraphName) {
        const result = await loadSandbox(sessionId);
        store.setSandboxGraphName(result.sandbox_graph);
        store.setProcessing(false);
        return;
      }

      // Step 10: approve
      if (step === 10 && sessionId) {
        await approveWizard(sessionId);
        store.setApproved(true);
        store.setProcessing(false);
        return;
      }

      // Advance step
      if (step < 10) {
        store.setStep(step + 1);
      }
    } catch (err: unknown) {
      // Extract detailed error from axios response
      let message = 'Step submission failed';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        const status = axiosErr.response?.status;
        const detail = axiosErr.response?.data?.detail;
        message = `Request failed (${status}): ${detail || 'Unknown error'}`;
      } else if (err instanceof Error) {
        message = err.message;
      }
      store.setError(message);
    }

    store.setProcessing(false);
  };

  const handleBack = () => {
    if (store.currentStep > 1) {
      store.setStep(store.currentStep - 1);
    }
  };

  const StepComponent = stepComponents[store.currentStep] || Step1Country;

  return (
    <div className="space-y-4">
      <WizardStepper currentStep={store.currentStep} />

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <StepComponent />
      </div>

      {store.sessionId && (store.isProcessing || store.currentStep === 4 || store.currentStep === 5) && (
        <AgentProgressPanel events={events} connected={connected} />
      )}

      {store.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
          {store.error}
          <button onClick={() => store.setError(null)} className="ml-2 text-red-600 underline text-xs">Dismiss</button>
        </div>
      )}

      <WizardNavigation
        currentStep={store.currentStep}
        onBack={handleBack}
        onNext={handleNext}
        canGoNext={canGoNext()}
        nextLabel={store.currentStep === 10 ? 'Approve & Load' : undefined}
        isProcessing={store.isProcessing}
      />
    </div>
  );
}
