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
      case 1: return !!store.originCountry && store.receivingCountries.length > 0;
      case 2: return !!store.scenarioType;
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
    const step = store.currentStep;

    if (step === 1 && !store.sessionId) {
      // Start session
      const { session_id } = await startWizardSession();
      store.setSessionId(session_id);
    }

    if (step <= 3 && store.sessionId) {
      store.setProcessing(true);
      try {
        const stepData: Record<number, Record<string, unknown>> = {
          1: { origin_country: store.originCountry, receiving_countries: store.receivingCountries },
          2: { scenario_type: store.scenarioType, data_categories: store.dataCategories },
          3: { rule_text: store.ruleText },
        };

        const result = await submitWizardStep(store.sessionId, { step, data: stepData[step] || {} });

        if (step === 3) {
          // AI processing happens - fetch full session to populate store
          if (result.status === 'failed') {
            store.setError(result.error_message || 'AI processing failed');
          } else {
            // Fetch the session state to get AI results
            const session = await getWizardSession(store.sessionId);
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
      } catch (err) {
        store.setError(err instanceof Error ? err.message : 'Step submission failed');
      }
      store.setProcessing(false);
    }

    if (step === 8 && store.sessionId && !store.sandboxGraphName) {
      store.setProcessing(true);
      try {
        const result = await loadSandbox(store.sessionId);
        store.setSandboxGraphName(result.sandbox_graph);
      } catch (err) {
        store.setError(err instanceof Error ? err.message : 'Sandbox load failed');
      }
      store.setProcessing(false);
      return;
    }

    if (step === 10 && store.sessionId) {
      store.setProcessing(true);
      try {
        await approveWizard(store.sessionId);
        store.setApproved(true);
      } catch (err) {
        store.setError(err instanceof Error ? err.message : 'Approval failed');
      }
      store.setProcessing(false);
      return;
    }

    if (step < 10) {
      store.setStep(step + 1);
    }
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
