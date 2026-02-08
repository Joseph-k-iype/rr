import { useState } from 'react';
import { useDropdownData } from '../../hooks/useDropdownData';
import { useEvaluation } from '../../hooks/useEvaluation';
import { useEvaluationStore } from '../../stores/evaluationStore';
import type { RulesEvaluationRequest } from '../../types/api';
import { LoadingSpinner } from '../common/LoadingSpinner';

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

  if (loadingDropdowns) return <LoadingSpinner message="Loading dropdown values..." />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await evaluate.mutateAsync(formData);
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
