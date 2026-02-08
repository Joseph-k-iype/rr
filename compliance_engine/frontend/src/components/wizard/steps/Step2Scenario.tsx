import { useState } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { useDropdownData } from '../../../hooks/useDropdownData';
import { LoadingSpinner } from '../../common/LoadingSpinner';

export function Step2Scenario() {
  const { scenarioType, dataCategories, receivingCountries, setScenarioType, setDataCategories, setReceivingCountries } = useWizardStore();
  const { data: dropdowns, isLoading } = useDropdownData();
  const [tagInput, setTagInput] = useState('');

  const addTags = (input: string) => {
    // Split by comma, trim, and add each non-empty unique tag
    const newTags = input
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0 && !dataCategories.includes(t));
    if (newTags.length > 0) {
      setDataCategories([...dataCategories, ...newTags]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ',') && tagInput.trim()) {
      e.preventDefault();
      addTags(tagInput);
      setTagInput('');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    // If user pastes or types something with a comma, auto-add the completed tags
    if (value.includes(',')) {
      const parts = value.split(',');
      // The last part (after the last comma) stays in the input as the user is still typing
      const completedParts = parts.slice(0, -1);
      const remaining = parts[parts.length - 1];
      const newTags = completedParts
        .map(t => t.trim())
        .filter(t => t.length > 0 && !dataCategories.includes(t));
      if (newTags.length > 0) {
        setDataCategories([...dataCategories, ...newTags]);
      }
      setTagInput(remaining);
    } else {
      setTagInput(value);
    }
  };

  const removeTag = (tag: string) => {
    setDataCategories(dataCategories.filter(c => c !== tag));
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 2: Scenario Type</h3>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Rule Type</label>
        <div className="flex gap-4">
          {['transfer', 'attribute'].map(type => (
            <label key={type} className={`flex items-center gap-2 p-3 border rounded-lg cursor-pointer ${
              scenarioType === type ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
            }`}>
              <input
                type="radio"
                value={type}
                checked={scenarioType === type}
                onChange={() => setScenarioType(type)}
              />
              <span className="text-sm font-medium capitalize">{type}</span>
            </label>
          ))}
        </div>
      </div>

      {scenarioType === 'transfer' && receivingCountries.length === 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Receiving Countries</label>
          <p className="text-xs text-gray-500 mb-2">Required for transfer-type rules. Select the countries that will receive data.</p>
          {isLoading ? <LoadingSpinner /> : (
            <>
              <select
                multiple
                value={receivingCountries}
                onChange={(e) => setReceivingCountries(Array.from(e.target.selectedOptions, o => o.value))}
                className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm h-32"
              >
                {dropdowns?.countries.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <p className="text-xs text-gray-500 mt-1">Hold Ctrl/Cmd to select multiple</p>
            </>
          )}
        </div>
      )}

      {scenarioType === 'transfer' && receivingCountries.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Receiving Countries</label>
          <div className="flex flex-wrap gap-2">
            {receivingCountries.map(c => (
              <span key={c} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                {c}
              </span>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1">Selected in Step 1</p>
        </div>
      )}

      {scenarioType === 'attribute' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Data Categories</label>
          <p className="text-xs text-gray-500 mb-2">Type a category and press Enter or comma to add it. You can also paste comma-separated values.</p>
          <div className="flex flex-wrap gap-2 mb-2">
            {dataCategories.map(cat => (
              <span key={cat} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                {cat}
                <button onClick={() => removeTag(cat)} className="text-blue-600 hover:text-blue-900">&times;</button>
              </span>
            ))}
          </div>
          <input
            value={tagInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="e.g. health records, credit scores, biometric data"
            className="w-full rounded-md border border-gray-300 py-2 px-3 text-sm"
          />
          {dataCategories.length > 0 && (
            <p className="text-xs text-green-600 mt-1">{dataCategories.length} categor{dataCategories.length === 1 ? 'y' : 'ies'} added</p>
          )}
        </div>
      )}
    </div>
  );
}
