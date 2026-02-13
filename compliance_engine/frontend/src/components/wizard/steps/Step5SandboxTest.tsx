import { useState } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { useDropdownData } from '../../../hooks/useDropdownData';
import { sandboxEvaluate } from '../../../services/wizardApi';
import { LoadingSpinner } from '../../common/LoadingSpinner';
import type { RulesEvaluationResponse } from '../../../types/api';

export function Step5SandboxTest() {
  const { sandboxGraphName, sessionId, isProcessing, sandboxTestResults, addSandboxTestResult, clearSandboxTestResults } = useWizardStore();
  const { data: dropdowns } = useDropdownData();

  const [evalForm, setEvalForm] = useState({
    origin_country: '',
    receiving_country: [] as string[],
    pii: false,
    purposes: [] as string[],
    process_l1: [] as string[],
    process_l2: [] as string[],
    process_l3: [] as string[],
  });
  const [evaluating, setEvaluating] = useState(false);
  const [latestResult, setLatestResult] = useState<RulesEvaluationResponse | null>(null);

  if (isProcessing && !sandboxGraphName) {
    return <LoadingSpinner message="Loading rule into sandbox..." />;
  }

  if (!sandboxGraphName) {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-900">Step 5: Sandbox Test</h3>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-5">
          <p className="text-sm text-blue-800 font-medium">Ready to Load</p>
          <p className="text-sm text-blue-700 mt-1">
            Click "Load Sandbox" to create a temporary sandbox graph and load the rule for testing.
          </p>
        </div>
      </div>
    );
  }

  const purposes = dropdowns?.purpose_of_processing?.length
    ? dropdowns.purpose_of_processing
    : (dropdowns?.purposes || []);

  const handleEvaluate = async () => {
    if (!sessionId) return;
    setEvaluating(true);
    clearSandboxTestResults();
    setLatestResult(null);
    try {
      const result = await sandboxEvaluate(sessionId, evalForm);
      setLatestResult(result as RulesEvaluationResponse);
      addSandboxTestResult(result);
    } catch {
      // handled by parent
    }
    setEvaluating(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-900">Step 5: Sandbox Test</h3>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full" />
          <span className="text-xs text-green-700 font-medium">Sandbox Ready</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Evaluation Form */}
        <div className="lg:col-span-3 card-dark p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-white mb-1">Origin Country</label>
              <select
                value={evalForm.origin_country}
                onChange={(e) => setEvalForm(f => ({ ...f, origin_country: e.target.value }))}
                className="input-dark text-sm"
              >
                <option value="">Select...</option>
                {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-white mb-1">Receiving Country</label>
              <select
                multiple
                value={evalForm.receiving_country}
                onChange={(e) => setEvalForm(f => ({ ...f, receiving_country: Array.from(e.target.selectedOptions, o => o.value) }))}
                className="input-dark text-sm h-20"
              >
                {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-white mb-1">Purpose Of Processing</label>
            <select
              multiple
              value={evalForm.purposes}
              onChange={(e) => setEvalForm(f => ({ ...f, purposes: Array.from(e.target.selectedOptions, o => o.value) }))}
              className="input-dark text-sm h-16"
            >
              {purposes.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-white mb-1">Process L1</label>
              <select multiple value={evalForm.process_l1} onChange={(e) => setEvalForm(f => ({ ...f, process_l1: Array.from(e.target.selectedOptions, o => o.value) }))} className="input-dark text-sm h-14">
                {dropdowns?.processes.l1.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-white mb-1">Process L2</label>
              <select multiple value={evalForm.process_l2} onChange={(e) => setEvalForm(f => ({ ...f, process_l2: Array.from(e.target.selectedOptions, o => o.value) }))} className="input-dark text-sm h-14">
                {dropdowns?.processes.l2.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-white mb-1">Process L3</label>
              <select multiple value={evalForm.process_l3} onChange={(e) => setEvalForm(f => ({ ...f, process_l3: Array.from(e.target.selectedOptions, o => o.value) }))} className="input-dark text-sm h-14">
                {dropdowns?.processes.l3.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          <button
            type="button"
            onClick={handleEvaluate}
            disabled={evaluating || !evalForm.origin_country}
            className="btn-red w-full"
          >
            {evaluating ? 'Evaluating...' : 'Evaluate Compliance'}
          </button>
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2 space-y-4">
          {!latestResult && sandboxTestResults.length === 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 text-sm">
              Run an evaluation to see results
            </div>
          )}

          {latestResult && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
              {latestResult.triggered_rules.map((rule, i) => (
                <div key={`${rule.rule_id}-${i}`} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-500">Rule {i + 1}</span>
                    <span className={rule.outcome === 'permission' ? 'badge-permission text-xs' : 'badge-prohibition text-xs'}>
                      {rule.outcome === 'permission' ? 'Permission' : 'Prohibition'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-800">{rule.rule_name}</p>
                  {rule.description && <p className="text-xs text-gray-500 mt-1">{rule.description}</p>}
                </div>
              ))}

              <div className="border-t pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-gray-900">Result</span>
                  <span className={`text-sm font-bold ${
                    latestResult.transfer_status === 'ALLOWED' ? 'text-green-600' :
                    latestResult.transfer_status === 'PROHIBITED' ? 'text-red-600' :
                    'text-yellow-600'
                  }`}>
                    {latestResult.transfer_status === 'ALLOWED' ? 'Permission' :
                     latestResult.transfer_status === 'PROHIBITED' ? 'Prohibition' :
                     latestResult.transfer_status}
                  </span>
                </div>
              </div>
            </div>
          )}

          {sandboxTestResults.length > 0 && (
            <div className="text-xs text-gray-500 text-center">
              {sandboxTestResults.length} test(s) run
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
