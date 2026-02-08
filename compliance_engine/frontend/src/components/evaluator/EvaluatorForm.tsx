import { useState } from 'react';
import { useDropdownData } from '../../hooks/useDropdownData';
import { useEvaluation } from '../../hooks/useEvaluation';
import { useEvaluationStore } from '../../stores/evaluationStore';
import type { RulesEvaluationRequest } from '../../types/api';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface MetadataEntry {
  key: string;
  value: string;
}

export function EvaluatorForm() {
  const { data: dropdowns, isLoading: loadingDropdowns } = useDropdownData();
  const evaluate = useEvaluation();
  const { setResult, setLoading, setError } = useEvaluationStore();

  const [formData, setFormData] = useState<RulesEvaluationRequest>({
    origin_country: '',
    receiving_country: '',
    pii: false,
    purposes: [],
    process_l1: [],
    process_l2: [],
    process_l3: [],
  });

  const [metadataEntries, setMetadataEntries] = useState<MetadataEntry[]>([]);
  const [jsonMode, setJsonMode] = useState(false);
  const [jsonInput, setJsonInput] = useState('');
  const [jsonError, setJsonError] = useState('');

  if (loadingDropdowns) return <LoadingSpinner message="Loading dropdown values..." />;

  const buildMetadata = (): Record<string, unknown> | undefined => {
    if (jsonMode) {
      if (!jsonInput.trim()) return undefined;
      try {
        const parsed = JSON.parse(jsonInput);
        setJsonError('');
        return parsed;
      } catch {
        setJsonError('Invalid JSON');
        return undefined;
      }
    }
    const filtered = metadataEntries.filter(e => e.key.trim());
    if (filtered.length === 0) return undefined;
    const obj: Record<string, unknown> = {};
    for (const entry of filtered) {
      obj[entry.key.trim()] = entry.value;
    }
    return obj;
  };

  const addMetadataEntry = () => {
    setMetadataEntries(prev => [...prev, { key: '', value: '' }]);
  };

  const removeMetadataEntry = (index: number) => {
    setMetadataEntries(prev => prev.filter((_, i) => i !== index));
  };

  const updateMetadataEntry = (index: number, field: 'key' | 'value', val: string) => {
    setMetadataEntries(prev => prev.map((e, i) => i === index ? { ...e, [field]: val } : e));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const metadata = buildMetadata();
      if (jsonMode && jsonInput.trim() && !metadata) {
        setError('Invalid JSON in metadata field');
        setLoading(false);
        return;
      }
      const payload = { ...formData, ...(metadata ? { metadata } : {}) };
      const result = await evaluate.mutateAsync(payload);
      setResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Evaluate Transfer Compliance</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Origin Country</label>
          <select
            value={formData.origin_country}
            onChange={(e) => setFormData(f => ({ ...f, origin_country: e.target.value }))}
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm"
            required
          >
            <option value="">Select...</option>
            {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Receiving Country</label>
          <select
            value={formData.receiving_country}
            onChange={(e) => setFormData(f => ({ ...f, receiving_country: e.target.value }))}
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm"
            required
          >
            <option value="">Select...</option>
            {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Purposes</label>
        <select
          multiple
          value={formData.purposes || []}
          onChange={(e) => setFormData(f => ({ ...f, purposes: Array.from(e.target.selectedOptions, o => o.value) }))}
          className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-24"
        >
          {dropdowns?.purposes.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Process L1</label>
          <select
            multiple
            value={formData.process_l1 || []}
            onChange={(e) => setFormData(f => ({ ...f, process_l1: Array.from(e.target.selectedOptions, o => o.value) }))}
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-24"
          >
            {dropdowns?.processes.l1.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Process L2</label>
          <select
            multiple
            value={formData.process_l2 || []}
            onChange={(e) => setFormData(f => ({ ...f, process_l2: Array.from(e.target.selectedOptions, o => o.value) }))}
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-24"
          >
            {dropdowns?.processes.l2.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Process L3</label>
          <select
            multiple
            value={formData.process_l3 || []}
            onChange={(e) => setFormData(f => ({ ...f, process_l3: Array.from(e.target.selectedOptions, o => o.value) }))}
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-24"
          >
            {dropdowns?.processes.l3.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="pii"
          checked={formData.pii}
          onChange={(e) => setFormData(f => ({ ...f, pii: e.target.checked }))}
          className="rounded border-gray-300"
        />
        <label htmlFor="pii" className="text-sm text-gray-700">Contains PII</label>
      </div>

      {/* Metadata Section */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">Metadata (for attribute detection)</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setJsonMode(false)}
              className={`text-xs px-2 py-1 rounded ${!jsonMode ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Key-Value
            </button>
            <button
              type="button"
              onClick={() => setJsonMode(true)}
              className={`text-xs px-2 py-1 rounded ${jsonMode ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-500 hover:text-gray-700'}`}
            >
              JSON
            </button>
          </div>
        </div>

        {jsonMode ? (
          <div>
            <textarea
              value={jsonInput}
              onChange={(e) => { setJsonInput(e.target.value); setJsonError(''); }}
              placeholder='{"data_type": "health_records", "sensitivity": "high"}'
              className={`w-full rounded-md border py-2 px-3 text-sm font-mono h-24 ${jsonError ? 'border-red-300' : 'border-gray-300'}`}
            />
            {jsonError && <p className="text-xs text-red-600 mt-1">{jsonError}</p>}
          </div>
        ) : (
          <div className="space-y-2">
            {metadataEntries.map((entry, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  value={entry.key}
                  onChange={(e) => updateMetadataEntry(i, 'key', e.target.value)}
                  placeholder="Key"
                  className="flex-1 rounded-md border border-gray-300 py-1.5 px-2 text-sm"
                />
                <input
                  value={entry.value}
                  onChange={(e) => updateMetadataEntry(i, 'value', e.target.value)}
                  placeholder="Value"
                  className="flex-1 rounded-md border border-gray-300 py-1.5 px-2 text-sm"
                />
                <button
                  type="button"
                  onClick={() => removeMetadataEntry(i)}
                  className="text-red-500 hover:text-red-700 text-sm px-1"
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={addMetadataEntry}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              + Add metadata entry
            </button>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={evaluate.isPending}
        className="w-full bg-blue-600 text-white py-2.5 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {evaluate.isPending ? 'Evaluating...' : 'Evaluate Compliance'}
      </button>
    </form>
  );
}
