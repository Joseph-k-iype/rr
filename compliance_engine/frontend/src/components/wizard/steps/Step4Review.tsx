import { useState, useEffect } from 'react';
import { useWizardStore } from '../../../stores/wizardStore';
import { editRule, editTerms } from '../../../services/wizardApi';

export function Step4Review() {
  const { editedRuleDefinition, editedTermsDictionary, dictionaryResult, sessionId, setEditedRuleDefinition } = useWizardStore();
  const rule = editedRuleDefinition as Record<string, unknown> | null;
  const terms = (editedTermsDictionary || dictionaryResult) as Record<string, unknown> | null;

  const [ruleId, setRuleId] = useState('');
  const [ruleName, setRuleName] = useState('');
  const [ruleDescription, setRuleDescription] = useState('');
  const [outcome, setOutcome] = useState('permission');
  const [actions, setActions] = useState('');
  const [duties, setDuties] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (rule) {
      setRuleId((rule.rule_id as string) || '');
      setRuleName((rule.name as string) || '');
      setRuleDescription((rule.description as string) || '');
      setOutcome((rule.outcome as string) || 'permission');
      const ruleActions = (rule.required_actions as string[]) || [];
      setActions(ruleActions.join(', '));
      // Extract ALL duties from ALL permissions
      const perms = rule.permissions as Array<{ duties?: Array<{ name?: string }> }> | undefined;
      const allDuties: string[] = [];
      (perms || []).forEach(p => {
        (p.duties || []).forEach(d => {
          if (d.name && !allDuties.includes(d.name)) {
            allDuties.push(d.name);
          }
        });
      });
      // Also check top-level duties field
      const topDuties = (rule.duties as string[]) || [];
      topDuties.forEach(d => {
        if (d && !allDuties.includes(d)) allDuties.push(d);
      });
      setDuties(allDuties.join(', '));
    }
  }, [rule]);

  const handleSave = async () => {
    if (!sessionId || !rule) return;
    setSaving(true);
    try {
      const updatedRule = {
        ...rule,
        rule_id: ruleId,
        name: ruleName,
        description: ruleDescription,
        outcome,
        required_actions: actions.split(',').map(s => s.trim()).filter(Boolean),
        duties: duties.split(',').map(s => s.trim()).filter(Boolean),
      };
      await editRule(sessionId, updatedRule);
      setEditedRuleDefinition(updatedRule);
      if (terms) {
        await editTerms(sessionId, terms);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // handled by parent error
    }
    setSaving(false);
  };

  if (!rule) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm">
        No rule definition available. Go back to Step 3 and submit a rule.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-900">Step 4: Review & Edit</h3>
        <button onClick={handleSave} disabled={saving} className="btn-red px-4 py-1.5 text-xs">
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      <div className="card-dark p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Rule ID</label>
            <input value={ruleId} onChange={(e) => setRuleId(e.target.value)} className="input-dark text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Permission / Prohibition</label>
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className="input-dark text-sm">
              <option value="permission">Permission</option>
              <option value="prohibition">Prohibition</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-300 mb-1">Rule Title</label>
          <input value={ruleName} onChange={(e) => setRuleName(e.target.value)} className="input-dark text-sm" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-300 mb-1">Rule Description</label>
          <textarea
            value={ruleDescription}
            onChange={(e) => setRuleDescription(e.target.value)}
            rows={3}
            className="input-dark text-sm resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Actions (System)</label>
            <input value={actions} onChange={(e) => setActions(e.target.value)} placeholder="Comma-separated: Anonymisation, Storage Limitation..." className="input-dark text-sm" />
            <p className="text-[10px] text-gray-500 mt-0.5">System-level: Anonymisation, Enhanced Security, Public Availability, Services Agreement, Storage Limitation, Outsourcing Agreement</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Duties (User)</label>
            <input value={duties} onChange={(e) => setDuties(e.target.value)} placeholder="Comma-separated: Consent, Consult/Approve Legal..." className="input-dark text-sm" />
            <p className="text-[10px] text-gray-500 mt-0.5">User-level: Consent, Consult/Approve Legal, Consult/Approve Risk, Notification to Regulator, Regulatory Approval, Explicit Consent</p>
          </div>
        </div>
      </div>

      {/* Data Dictionaries */}
      {terms && (
        <div className="card-dark p-5 space-y-3">
          <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wide">Data Dictionaries</h4>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {Object.entries(terms).map(([key, value]) => {
              if (key === 'name' || key === 'description') return null;
              if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                return (
                  <div key={key} className="border border-gray-700 rounded-lg p-3">
                    <p className="text-xs font-semibold text-gray-300 mb-1 capitalize">{key.replace(/_/g, ' ')}</p>
                    {Object.entries(value as Record<string, unknown>).map(([subKey, subValue]) => (
                      <div key={subKey} className="ml-2 mb-1">
                        <span className="text-xs text-gray-500">{subKey}: </span>
                        <span className="text-xs text-gray-300">
                          {Array.isArray(subValue) ? subValue.join(', ') : String(subValue)}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              }
              if (Array.isArray(value)) {
                return (
                  <div key={key} className="border border-gray-700 rounded-lg p-3">
                    <p className="text-xs font-semibold text-gray-300 mb-1 capitalize">{key.replace(/_/g, ' ')}</p>
                    <p className="text-xs text-gray-400">{(value as string[]).join(', ')}</p>
                  </div>
                );
              }
              return (
                <div key={key} className="flex gap-2 text-xs">
                  <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                  <span className="text-gray-300">{String(value)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metadata summary */}
      <div className="card-dark p-5 space-y-2">
        <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wide">Metadata</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div><span className="text-gray-500">Origin:</span> <span className="text-white">{(rule.origin_group as string) || (rule.origin_countries as string[])?.join(', ') || 'Any'}</span></div>
          <div><span className="text-gray-500">Receiving:</span> <span className="text-white">{(rule.receiving_group as string) || (rule.receiving_countries as string[])?.join(', ') || 'Any'}</span></div>
          <div><span className="text-gray-500">Type:</span> <span className="text-white">{(rule.rule_type as string) || '—'}</span></div>
          <div><span className="text-gray-500">Priority:</span> <span className="text-white">{String(rule.priority || '—')}</span></div>
          <div><span className="text-gray-500">PII:</span> <span className="text-white">{rule.requires_pii ? 'Yes' : 'No'}</span></div>
          <div><span className="text-gray-500">ODRL:</span> <span className="text-white">{(rule.odrl_type as string) || '—'}</span></div>
        </div>
      </div>
    </div>
  );
}
