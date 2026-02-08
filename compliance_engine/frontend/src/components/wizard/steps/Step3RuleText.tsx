import { useWizardStore } from '../../../stores/wizardStore';

export function Step3RuleText() {
  const { ruleText, setRuleText } = useWizardStore();

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 3: Enter Rule Text</h3>
      <p className="text-sm text-gray-600">
        Describe the compliance rule in natural language. The AI agents will analyze it and generate a machine-readable rule definition.
      </p>
      <textarea
        value={ruleText}
        onChange={(e) => setRuleText(e.target.value)}
        placeholder="e.g., Personal health data from the United Kingdom should not be transferred to China without a completed PIA and TIA..."
        className="w-full h-40 rounded-md border border-gray-300 py-2 px-3 text-sm resize-none"
      />
      <p className="text-xs text-gray-400">{ruleText.length} characters</p>
    </div>
  );
}
