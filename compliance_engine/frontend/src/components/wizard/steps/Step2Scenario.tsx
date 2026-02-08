import { useWizardStore } from '../../../stores/wizardStore';

const DATA_CATEGORIES = ['health_data', 'financial_data', 'biometric_data', 'location_data'];

export function Step2Scenario() {
  const { scenarioType, dataCategories, setScenarioType, setDataCategories } = useWizardStore();

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
      {scenarioType === 'attribute' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Data Categories</label>
          <div className="space-y-2">
            {DATA_CATEGORIES.map(cat => (
              <label key={cat} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={dataCategories.includes(cat)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setDataCategories([...dataCategories, cat]);
                    } else {
                      setDataCategories(dataCategories.filter(c => c !== cat));
                    }
                  }}
                  className="rounded border-gray-300"
                />
                <span className="text-sm">{cat.replaceAll('_', ' ')}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
