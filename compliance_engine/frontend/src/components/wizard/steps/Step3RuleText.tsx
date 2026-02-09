import { useWizardStore } from '../../../stores/wizardStore';

export function Step3RuleText() {
  const { ruleText, setRuleText, isPiiRelated, setIsPiiRelated } = useWizardStore();

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-xs font-medium uppercase tracking-widest text-gray-900 mb-1">Rule Text</h3>
        <p className="text-[11px] text-gray-400">
          Describe the compliance rule in natural language. The AI agents will analyze it and generate a machine-readable definition.
        </p>
      </div>

      <textarea
        value={ruleText}
        onChange={(e) => setRuleText(e.target.value)}
        placeholder="e.g., Customer financial data originating from the EU must not be transferred to jurisdictions without an adequacy decision unless SCCs are in place and a TIA has been completed..."
        className="w-full h-40 rounded border border-gray-200 py-2.5 px-3 text-sm text-gray-900 placeholder:text-gray-300 resize-none focus:outline-none focus:border-gray-400 transition-colors"
      />

      <div className="flex items-center justify-between">
        <p className="text-[10px] text-gray-300 tabular-nums">{ruleText.length} characters</p>

        <label className="flex items-center gap-2 cursor-pointer select-none group">
          <div className="relative">
            <input
              type="checkbox"
              checked={isPiiRelated}
              onChange={(e) => setIsPiiRelated(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-8 h-[18px] rounded-full bg-gray-200 peer-checked:bg-gray-900 transition-colors" />
            <div className="absolute top-[3px] left-[3px] w-3 h-3 rounded-full bg-white transition-transform peer-checked:translate-x-[14px]" />
          </div>
          <span className="text-xs text-gray-500 group-hover:text-gray-700 transition-colors">
            PII Related
          </span>
        </label>
      </div>

      {isPiiRelated && (
        <p className="text-[11px] text-gray-400 bg-gray-50 rounded px-3 py-2">
          This rule will be marked as involving Personally Identifiable Information. The AI agents will factor PII requirements into the analysis, graph properties, and compliance checks.
        </p>
      )}
    </div>
  );
}
