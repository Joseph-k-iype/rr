import { useState } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { useDropdownData } from '../../../hooks/useDropdownData';
import { sandboxEvaluate } from '../../../services/wizardApi';
import { StatusBadge } from '../../common/StatusBadge';

export function Step9Test() {
  const { sessionId, sandboxTestResults, addSandboxTestResult } = useWizardStore();
  const { data: dropdowns } = useDropdownData();
  const [origin, setOrigin] = useState('');
  const [receiving, setReceiving] = useState('');
  const [pii, setPii] = useState(false);
  const [testing, setTesting] = useState(false);

  const runTest = async () => {
    if (!sessionId) return;
    setTesting(true);
    try {
      const response = await sandboxEvaluate(sessionId, {
        origin_country: origin,
        receiving_country: receiving,
        pii,
      });
      // Backend returns {result, test_number} - unwrap to get actual evaluation result
      addSandboxTestResult(response.result || response);
    } catch (err) {
      addSandboxTestResult({ error: String(err) });
    }
    setTesting(false);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 9: Sandbox Testing</h3>

      <div className="grid grid-cols-2 gap-4">
        <select value={origin} onChange={e => setOrigin(e.target.value)} className="rounded-md border border-gray-300 py-2 px-3 text-sm">
          <option value="">Origin...</option>
          {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={receiving} onChange={e => setReceiving(e.target.value)} className="rounded-md border border-gray-300 py-2 px-3 text-sm">
          <option value="">Receiving...</option>
          {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={pii} onChange={e => setPii(e.target.checked)} className="rounded" />
        Contains PII
      </label>

      <button
        onClick={runTest}
        disabled={testing || !origin || !receiving}
        className="bg-blue-600 text-white px-4 py-2 text-sm rounded-md hover:bg-blue-700 disabled:opacity-40"
      >
        {testing ? 'Running...' : 'Run Test'}
      </button>

      {sandboxTestResults.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Test Results</h4>
          {sandboxTestResults.map((r, i) => {
            const status = r.transfer_status as string | undefined;
            return (
              <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium">Test {i + 1}</span>
                  {status && <StatusBadge status={status} />}
                </div>
                <pre className="text-gray-600 overflow-auto max-h-24">
                  {JSON.stringify(r, null, 2)}
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
