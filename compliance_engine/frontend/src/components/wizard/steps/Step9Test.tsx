import { useState } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { useDropdownData } from '../../../hooks/useDropdownData';
import { sandboxEvaluate } from '../../../services/wizardApi';
import { StatusBadge } from '../../common/StatusBadge';

interface MetadataEntry { key: string; value: string }

export function Step9Test() {
  const { sessionId, sandboxTestResults, addSandboxTestResult } = useWizardStore();
  const { data: dropdowns } = useDropdownData();
  const [origin, setOrigin] = useState('');
  const [receiving, setReceiving] = useState('');
  const [pii, setPii] = useState(false);
  const [purposes, setPurposes] = useState<string[]>([]);
  const [metadataEntries, setMetadataEntries] = useState<MetadataEntry[]>([]);
  const [testing, setTesting] = useState(false);

  const runTest = async () => {
    if (!sessionId) return;
    setTesting(true);
    try {
      const metadata: Record<string, string> = {};
      metadataEntries.filter(e => e.key.trim()).forEach(e => { metadata[e.key.trim()] = e.value; });

      const response = await sandboxEvaluate(sessionId, {
        origin_country: origin,
        receiving_country: receiving,
        pii,
        purposes: purposes.length > 0 ? purposes : undefined,
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      });
      addSandboxTestResult(response.result || response);
    } catch (err) {
      addSandboxTestResult({ error: String(err), transfer_status: 'ERROR' });
    }
    setTesting(false);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Sandbox Testing</h3>
      <p className="text-sm text-gray-600">Test the rule with different inputs before approving.</p>

      {/* Test Form */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Origin Country</label>
            <select value={origin} onChange={e => setOrigin(e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm">
              <option value="">Select origin...</option>
              {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Receiving Country</label>
            <select value={receiving} onChange={e => setReceiving(e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm">
              <option value="">Select receiving...</option>
              {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Purposes</label>
          <select
            multiple
            value={purposes}
            onChange={e => setPurposes(Array.from(e.target.selectedOptions, o => o.value))}
            className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm h-20"
          >
            {dropdowns?.purposes.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={pii} onChange={e => setPii(e.target.checked)} className="rounded border-gray-300" />
          <span className="text-xs text-gray-700">Contains PII</span>
        </label>

        {/* Metadata */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Metadata (for attribute detection)</label>
          <div className="space-y-1.5">
            {metadataEntries.map((entry, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  value={entry.key}
                  onChange={e => setMetadataEntries(prev => prev.map((en, idx) => idx === i ? { ...en, key: e.target.value } : en))}
                  placeholder="Key"
                  className="flex-1 rounded-md border border-gray-300 py-1 px-2 text-xs"
                />
                <input
                  value={entry.value}
                  onChange={e => setMetadataEntries(prev => prev.map((en, idx) => idx === i ? { ...en, value: e.target.value } : en))}
                  placeholder="Value"
                  className="flex-1 rounded-md border border-gray-300 py-1 px-2 text-xs"
                />
                <button type="button" onClick={() => setMetadataEntries(prev => prev.filter((_, idx) => idx !== i))} className="text-red-400 hover:text-red-600 text-xs">&times;</button>
              </div>
            ))}
            <button type="button" onClick={() => setMetadataEntries(prev => [...prev, { key: '', value: '' }])} className="text-xs text-blue-600 hover:text-blue-800">
              + Add metadata
            </button>
          </div>
        </div>

        <button
          onClick={runTest}
          disabled={testing || !origin || !receiving}
          className="bg-blue-600 text-white px-4 py-2 text-sm rounded-md hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          {testing ? 'Running...' : 'Run Test'}
        </button>
      </div>

      {/* Test Results */}
      {sandboxTestResults.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-900">Test Results ({sandboxTestResults.length})</h4>
          {sandboxTestResults.map((r, i) => {
            const result = r as Record<string, unknown>;
            const status = (result.transfer_status as string) || '';
            const message = (result.message as string) || '';
            const triggeredRules = (result.triggered_rules as Record<string, unknown>[]) || [];
            const prohibReasons = (result.prohibition_reasons as string[]) || [];
            const detectedAttrs = (result.detected_attributes as Record<string, unknown>[]) || [];
            const isError = !!result.error;

            return (
              <div key={i} className={`rounded-lg border p-4 ${
                isError ? 'bg-red-50 border-red-200' :
                status === 'ALLOWED' ? 'bg-green-50 border-green-200' :
                status === 'PROHIBITED' ? 'bg-red-50 border-red-200' :
                'bg-yellow-50 border-yellow-200'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-500">Test {i + 1}</span>
                  {status && <StatusBadge status={status} />}
                </div>

                {message && <p className="text-sm text-gray-700 mb-2">{message}</p>}

                {isError && <p className="text-sm text-red-700">{result.error as string}</p>}

                {triggeredRules.length > 0 && (
                  <div className="mt-2">
                    <span className="text-xs text-gray-500">Triggered Rules:</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {triggeredRules.map((tr, j) => (
                        <span key={j} className="text-xs bg-white border border-gray-200 rounded px-2 py-0.5">
                          {(tr.rule_name as string) || (tr.rule_id as string)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {prohibReasons.length > 0 && (
                  <div className="mt-2">
                    <span className="text-xs text-red-600">Prohibition Reasons:</span>
                    <ul className="mt-0.5 space-y-0.5">
                      {prohibReasons.map((reason, j) => (
                        <li key={j} className="text-xs text-red-700">&bull; {reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {detectedAttrs.length > 0 && (
                  <div className="mt-2">
                    <span className="text-xs text-purple-600">Detected Attributes:</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {detectedAttrs.map((attr, j) => (
                        <span key={j} className="text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">
                          {(attr.attribute_name as string)} ({Math.round(((attr.confidence as number) || 0) * 100)}%)
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <details className="mt-2 text-xs">
                  <summary className="text-gray-400 cursor-pointer hover:text-gray-600">Raw result</summary>
                  <pre className="bg-white/50 p-2 rounded mt-1 overflow-auto max-h-32 text-gray-600">
                    {JSON.stringify(r, null, 2)}
                  </pre>
                </details>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
