import { useState, useEffect } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { editRule, editTerms } from '../../../services/wizardApi';

interface MetadataEntry { key: string; value: string }

function TagInput({ label, values, onChange, placeholder }: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState('');

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !values.includes(trimmed)) {
      onChange([...values, trimmed]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ',') && input.trim()) {
      e.preventDefault();
      addTag(input);
      setInput('');
    }
  };

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <div className="flex flex-wrap gap-1 mb-1.5">
        {values.map(v => (
          <span key={v} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs border border-blue-200">
            {v}
            <button type="button" onClick={() => onChange(values.filter(x => x !== v))} className="text-blue-400 hover:text-blue-700">&times;</button>
          </span>
        ))}
      </div>
      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm"
      />
    </div>
  );
}

export function Step7Edit() {
  const { sessionId, editedRuleDefinition, editedTermsDictionary, setEditedRuleDefinition, setEditedTermsDictionary } = useWizardStore();
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [rawJson, setRawJson] = useState('');
  const [jsonError, setJsonError] = useState('');

  // Local form state derived from the rule definition
  const rule = (editedRuleDefinition || {}) as Record<string, unknown>;
  const [formState, setFormState] = useState({
    rule_id: (rule.rule_id as string) || '',
    name: (rule.name as string) || '',
    description: (rule.description as string) || '',
    rule_type: (rule.rule_type as string) || 'transfer',
    outcome: (rule.outcome as string) || 'permission',
    priority: (rule.priority as string) || 'medium',
    odrl_type: (rule.odrl_type as string) || 'Permission',
    origin_group: (rule.origin_group as string) || '',
    receiving_group: (rule.receiving_group as string) || '',
    origin_countries: (rule.origin_countries as string[]) || [],
    receiving_countries: (rule.receiving_countries as string[]) || [],
    requires_pii: (rule.requires_pii as boolean) || false,
    attribute_name: (rule.attribute_name as string) || '',
    attribute_keywords: (rule.attribute_keywords as string[]) || [],
    required_actions: (rule.required_actions as string[]) || [],
    odrl_action: (rule.odrl_action as string) || 'transfer',
    odrl_target: (rule.odrl_target as string) || 'Data',
  });

  // Terms dictionary entries
  const [termsEntries, setTermsEntries] = useState<MetadataEntry[]>(() => {
    if (!editedTermsDictionary) return [];
    const dict = editedTermsDictionary as Record<string, unknown>;
    return Object.entries(dict).map(([key, val]) => ({
      key,
      value: typeof val === 'string' ? val : JSON.stringify(val),
    }));
  });

  useEffect(() => {
    setRawJson(JSON.stringify(editedRuleDefinition, null, 2));
  }, [editedRuleDefinition]);

  const updateField = (field: string, value: unknown) => {
    setFormState(prev => ({ ...prev, [field]: value }));
  };

  const buildRuleFromForm = () => {
    const built: Record<string, unknown> = { ...formState };
    // Clean empty arrays/strings
    if (!built.origin_group) delete built.origin_group;
    if (!built.receiving_group) delete built.receiving_group;
    if ((built.origin_countries as string[]).length === 0) delete built.origin_countries;
    if ((built.receiving_countries as string[]).length === 0) delete built.receiving_countries;
    if (!built.attribute_name) delete built.attribute_name;
    if ((built.attribute_keywords as string[]).length === 0) delete built.attribute_keywords;
    // Sync odrl_type with outcome
    built.odrl_type = built.outcome === 'prohibition' ? 'Prohibition' : 'Permission';
    return built;
  };

  const handleSaveRule = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      let ruleData: Record<string, unknown>;
      if (showRawJson) {
        ruleData = JSON.parse(rawJson);
        setJsonError('');
      } else {
        ruleData = buildRuleFromForm();
      }
      setEditedRuleDefinition(ruleData);
      if (sessionId) {
        await editRule(sessionId, ruleData);
      }
      setSaveMsg('Rule saved');
    } catch (e) {
      if (e instanceof SyntaxError) setJsonError('Invalid JSON');
      else setSaveMsg(`Error: ${e}`);
    }
    setSaving(false);
  };

  const handleSaveTerms = async () => {
    setSaving(true);
    const termsObj: Record<string, string> = {};
    termsEntries.filter(e => e.key.trim()).forEach(e => { termsObj[e.key.trim()] = e.value; });
    setEditedTermsDictionary(termsObj);
    if (sessionId) {
      try { await editTerms(sessionId, termsObj); } catch { /* ignore */ }
    }
    setSaveMsg('Terms saved');
    setSaving(false);
  };

  return (
    <div className="space-y-5">
      <h3 className="text-lg font-semibold text-gray-900">Edit Rule & Terms</h3>

      {/* Rule Editor */}
      <div className="border border-gray-200 rounded-lg">
        <div className="flex items-center justify-between bg-gray-50 px-4 py-2.5 border-b border-gray-200">
          <h4 className="text-sm font-medium text-gray-900">Rule Definition</h4>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowRawJson(!showRawJson)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              {showRawJson ? 'Form View' : 'JSON View'}
            </button>
            <button
              onClick={handleSaveRule}
              disabled={saving}
              className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Rule'}
            </button>
          </div>
        </div>

        {showRawJson ? (
          <div className="p-4">
            <textarea
              value={rawJson}
              onChange={e => { setRawJson(e.target.value); setJsonError(''); }}
              className={`w-full h-64 rounded-md border py-2 px-3 text-xs font-mono resize-none ${jsonError ? 'border-red-300' : 'border-gray-300'}`}
            />
            {jsonError && <p className="text-xs text-red-600 mt-1">{jsonError}</p>}
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Row 1: ID, Name */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Rule ID</label>
                <input value={formState.rule_id} onChange={e => updateField('rule_id', e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm font-mono" />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Name</label>
                <input value={formState.name} onChange={e => updateField('name', e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm" />
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Description</label>
              <textarea value={formState.description} onChange={e => updateField('description', e.target.value)} rows={2} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm resize-none" />
            </div>

            {/* Row 2: Type, Outcome, Priority */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Rule Type</label>
                <select value={formState.rule_type} onChange={e => updateField('rule_type', e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm">
                  <option value="transfer">Transfer</option>
                  <option value="attribute">Attribute</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Outcome</label>
                <select value={formState.outcome} onChange={e => updateField('outcome', e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm">
                  <option value="permission">Permission</option>
                  <option value="prohibition">Prohibition</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Priority</label>
                <select value={formState.priority} onChange={e => updateField('priority', e.target.value)} className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm">
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            {/* Countries */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Origin Group</label>
                <input value={formState.origin_group} onChange={e => updateField('origin_group', e.target.value)} placeholder="e.g. EU_EEA" className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Receiving Group</label>
                <input value={formState.receiving_group} onChange={e => updateField('receiving_group', e.target.value)} placeholder="e.g. NON_ADEQUATE" className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TagInput label="Origin Countries" values={formState.origin_countries} onChange={v => updateField('origin_countries', v)} placeholder="Add country, press Enter" />
              <TagInput label="Receiving Countries" values={formState.receiving_countries} onChange={v => updateField('receiving_countries', v)} placeholder="Add country, press Enter" />
            </div>

            {/* PII & Actions */}
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={formState.requires_pii} onChange={e => updateField('requires_pii', e.target.checked)} className="rounded border-gray-300" />
                <span className="text-xs text-gray-700">Requires PII</span>
              </label>
            </div>

            {/* Attribute fields (only for attribute type) */}
            {formState.rule_type === 'attribute' && (
              <div className="border-t border-gray-200 pt-3 space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Attribute Name</label>
                  <input value={formState.attribute_name} onChange={e => updateField('attribute_name', e.target.value)} placeholder="e.g. health_data" className="w-full rounded-md border border-gray-300 py-1.5 px-2 text-sm" />
                </div>
                <TagInput label="Attribute Keywords" values={formState.attribute_keywords} onChange={v => updateField('attribute_keywords', v)} placeholder="Add keyword, press Enter" />
              </div>
            )}

            <TagInput label="Required Actions" values={formState.required_actions} onChange={v => updateField('required_actions', v)} placeholder="e.g. Complete TIA, press Enter" />
          </div>
        )}
      </div>

      {/* Terms Dictionary Editor */}
      <div className="border border-gray-200 rounded-lg">
        <div className="flex items-center justify-between bg-gray-50 px-4 py-2.5 border-b border-gray-200">
          <h4 className="text-sm font-medium text-gray-900">Terms Dictionary</h4>
          <button onClick={handleSaveTerms} disabled={saving} className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Terms'}
          </button>
        </div>
        <div className="p-4 space-y-2">
          {termsEntries.map((entry, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input
                value={entry.key}
                onChange={e => setTermsEntries(prev => prev.map((en, idx) => idx === i ? { ...en, key: e.target.value } : en))}
                placeholder="Term"
                className="flex-1 rounded-md border border-gray-300 py-1.5 px-2 text-sm"
              />
              <input
                value={entry.value}
                onChange={e => setTermsEntries(prev => prev.map((en, idx) => idx === i ? { ...en, value: e.target.value } : en))}
                placeholder="Definition"
                className="flex-[2] rounded-md border border-gray-300 py-1.5 px-2 text-sm"
              />
              <button type="button" onClick={() => setTermsEntries(prev => prev.filter((_, idx) => idx !== i))} className="text-red-400 hover:text-red-600 text-sm px-1">&times;</button>
            </div>
          ))}
          <button type="button" onClick={() => setTermsEntries(prev => [...prev, { key: '', value: '' }])} className="text-xs text-blue-600 hover:text-blue-800">
            + Add term
          </button>
        </div>
      </div>

      {saveMsg && (
        <p className={`text-xs ${saveMsg.startsWith('Error') ? 'text-red-600' : 'text-green-600'}`}>{saveMsg}</p>
      )}
    </div>
  );
}
