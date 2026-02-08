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
  // Only connect SSE when step >= 3 (agent processing). Steps 1-2 have no agent activity.
  const sseSessionId = store.currentStep >= 3 ? store.sessionId : null;
  const { events, connected } = useAgentEvents(sseSessionId);

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
      // Step 8: allow Next if sandbox loaded, OR allow retry (Next acts as "Load Sandbox")
      case 8: return !!store.editedRuleDefinition;
      case 9: return store.sandboxTestResults.length > 0;
      case 10: return true;
      default: return false;
    }
  }, [store]);

  const getNextLabel = () => {
    const step = store.currentStep;
    if (step === 8 && !store.sandboxGraphName) return 'Load Sandbox';
    if (step === 10) return 'Approve & Load';
    return 'Next';
  };

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
            store.setError(result.error_message || 'AI processing failed. You can go Back and resubmit.');
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

      // Step 8: load sandbox (or retry if previous attempt failed)
      if (step === 8 && sessionId && !state.sandboxGraphName) {
        try {
          const result = await loadSandbox(sessionId);
          store.setSandboxGraphName(result.sandbox_graph);
        } catch (sandboxErr: unknown) {
          let msg = 'Failed to load sandbox';
          if (sandboxErr && typeof sandboxErr === 'object' && 'response' in sandboxErr) {
            const axiosErr = sandboxErr as { response?: { data?: { detail?: string } } };
            msg = axiosErr.response?.data?.detail || msg;
          } else if (sandboxErr instanceof Error) {
            msg = sandboxErr.message;
          }
          store.setError(`Sandbox Error: ${msg}. You can go Back to edit the rule and try again.`);
          store.setProcessing(false);
          return;
        }
        store.setProcessing(false);
        // Don't auto-advance — user sees sandbox loaded status, clicks Next to go to test
        return;
      }

      // Step 8: sandbox already loaded, just advance
      if (step === 8 && state.sandboxGraphName) {
        store.setStep(9);
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
      store.setError(null);
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
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-red-800">Error</p>
              <p className="text-sm text-red-700 mt-0.5">{store.error}</p>
            </div>
            <button onClick={() => store.setError(null)} className="text-red-400 hover:text-red-600 text-sm ml-3 shrink-0">&times;</button>
          </div>
        </div>
      )}

      <WizardNavigation
        currentStep={store.currentStep}
        onBack={handleBack}
        onNext={handleNext}
        canGoNext={canGoNext()}
        nextLabel={getNextLabel()}
        isProcessing={store.isProcessing}
      />
    </div>
  );
}
