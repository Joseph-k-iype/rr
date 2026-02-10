import { useState, useMemo } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { useDropdownData } from '../../../hooks/useDropdownData';
import { LoadingSpinner } from '../../common/LoadingSpinner';
import type { DictionaryEntry } from '../../../types/api';

function GroupedMultiSelect({
  label,
  entries,
  selected,
  onChange,
}: {
  label: string;
  entries: DictionaryEntry[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const grouped = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const e of entries) {
      const cat = e.category || 'Other';
      (map[cat] ??= []).push(e.name);
    }
    return map;
  }, [entries]);

  const toggle = (name: string) => {
    onChange(
      selected.includes(name)
        ? selected.filter(s => s !== name)
        : [...selected, name]
    );
  };

  return (
    <details className="mt-4">
      <summary className="text-sm font-medium text-gray-700 cursor-pointer select-none">
        {label} (optional)
        {selected.length > 0 && (
          <span className="ml-2 text-xs text-blue-600">{selected.length} selected</span>
        )}
      </summary>
      <div className="mt-2">
        {selected.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {selected.map(s => (
              <span key={s} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full text-xs">
                {s}
                <button onClick={() => toggle(s)} className="text-blue-600 hover:text-blue-900">&times;</button>
              </span>
            ))}
          </div>
        )}
        <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-md p-2 space-y-2">
          {Object.entries(grouped).map(([category, names]) => (
            <div key={category}>
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{category}</div>
              <div className="flex flex-wrap gap-1">
                {names.map(name => (
                  <label
                    key={name}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs cursor-pointer transition-colors ${
                      selected.includes(name) ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(name)}
                      onChange={() => toggle(name)}
                      className="sr-only"
                    />
                    {name}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

export function Step2Scenario() {
  const {
    scenarioType, dataCategories, receivingCountries,
    selectedProcesses, selectedPurposes, selectedDataSubjects, selectedGdc,
    setScenarioType, setDataCategories, setReceivingCountries,
    setSelectedProcesses, setSelectedPurposes, setSelectedDataSubjects, setSelectedGdc,
  } = useWizardStore();
  const { data: dropdowns, isLoading } = useDropdownData();
  const [tagInput, setTagInput] = useState('');

  const addTags = (input: string) => {
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
    if (value.includes(',')) {
      const parts = value.split(',');
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

      {/* Optional dictionary-based selectors */}
      {!isLoading && dropdowns && (
        <>
          {dropdowns.processes_dict?.length > 0 && (
            <GroupedMultiSelect
              label="Processes"
              entries={dropdowns.processes_dict}
              selected={selectedProcesses}
              onChange={setSelectedProcesses}
            />
          )}
          {dropdowns.purposes_dict?.length > 0 && (
            <GroupedMultiSelect
              label="Purposes"
              entries={dropdowns.purposes_dict}
              selected={selectedPurposes}
              onChange={setSelectedPurposes}
            />
          )}
          {dropdowns.data_subjects?.length > 0 && (
            <GroupedMultiSelect
              label="Data Subjects"
              entries={dropdowns.data_subjects}
              selected={selectedDataSubjects}
              onChange={setSelectedDataSubjects}
            />
          )}
          {dropdowns.gdc?.length > 0 && (
            <GroupedMultiSelect
              label="Global Data Categories"
              entries={dropdowns.gdc}
              selected={selectedGdc}
              onChange={setSelectedGdc}
            />
          )}
        </>
      )}
    </div>
  );
}
