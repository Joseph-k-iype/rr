import { useDropdownData } from '../../../hooks/useDropdownData';
import { useWizardStore } from '../../../stores/wizardStore';
import { LoadingSpinner } from '../../common/LoadingSpinner';

export function Step1Country() {
  const { data: dropdowns, isLoading } = useDropdownData();
  const { originCountry, receivingCountries, setOriginCountry, setReceivingCountries } = useWizardStore();

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 1: Select Countries</h3>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Origin Country</label>
        <select
          value={originCountry}
          onChange={(e) => setOriginCountry(e.target.value)}
          className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm"
        >
          <option value="">Select origin country...</option>
          {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Receiving Countries</label>
        <select
          multiple
          value={receivingCountries}
          onChange={(e) => setReceivingCountries(Array.from(e.target.selectedOptions, o => o.value))}
          className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-32"
        >
          {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <p className="text-xs text-gray-500 mt-1">Hold Ctrl/Cmd to select multiple</p>
        <p className="text-xs text-gray-400 mt-0.5">Leave empty to apply the rule to all receiving countries</p>
      </div>
    </div>
  );
}
