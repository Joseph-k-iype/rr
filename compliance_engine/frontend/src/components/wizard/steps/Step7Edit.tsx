import { useState } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { editRule, editTerms } from '../../../services/wizardApi';

export function Step7Edit() {
  const { sessionId, editedRuleDefinition, editedTermsDictionary, setEditedRuleDefinition, setEditedTermsDictionary } = useWizardStore();
  const [ruleJson, setRuleJson] = useState(editedRuleDefinition ? JSON.stringify(editedRuleDefinition, null, 2) : '{}');
  const [termsJson, setTermsJson] = useState(editedTermsDictionary ? JSON.stringify(editedTermsDictionary, null, 2) : '{}');
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [termsError, setTermsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleRuleSave = async () => {
    try {
      const parsed = JSON.parse(ruleJson);
      setEditedRuleDefinition(parsed);
      setRuleError(null);
      if (sessionId) {
        setSaving(true);
        await editRule(sessionId, parsed);
        setSaving(false);
      }
    } catch (e) {
      setSaving(false);
      setRuleError(e instanceof SyntaxError ? 'Invalid JSON' : String(e));
    }
  };

  const handleTermsSave = async () => {
    try {
      const parsed = JSON.parse(termsJson);
      setEditedTermsDictionary(parsed);
      setTermsError(null);
      if (sessionId) {
        setSaving(true);
        await editTerms(sessionId, parsed);
        setSaving(false);
      }
    } catch (e) {
      setSaving(false);
      setTermsError(e instanceof SyntaxError ? 'Invalid JSON' : String(e));
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Step 7: Edit Rule & Terms</h3>

      <div>
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-sm font-medium text-gray-900">Rule Definition</h4>
          <button onClick={handleRuleSave} disabled={saving} className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50">{saving ? 'Saving...' : 'Save Changes'}</button>
        </div>
        <textarea
          value={ruleJson}
          onChange={(e) => setRuleJson(e.target.value)}
          className="w-full h-48 rounded-md border border-gray-300 py-2 px-3 text-xs font-mono resize-none"
        />
        {ruleError && <p className="text-xs text-red-600 mt-1">{ruleError}</p>}
      </div>

      <div>
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-sm font-medium text-gray-900">Terms Dictionary</h4>
          <button onClick={handleTermsSave} disabled={saving} className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50">{saving ? 'Saving...' : 'Save Changes'}</button>
        </div>
        <textarea
          value={termsJson}
          onChange={(e) => setTermsJson(e.target.value)}
          className="w-full h-36 rounded-md border border-gray-300 py-2 px-3 text-xs font-mono resize-none"
        />
        {termsError && <p className="text-xs text-red-600 mt-1">{termsError}</p>}
      </div>
    </div>
  );
}
