import { useWizardStore } from '../../../stores/wizardStore';

export function Step5Dictionary() {
  const { dictionaryResult } = useWizardStore();

  if (!dictionaryResult) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Generated Dictionary</h3>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-500">No dictionary generated. This is normal for transfer-type rules.</p>
          <p className="text-xs text-gray-400 mt-1">Click Next to continue.</p>
        </div>
      </div>
    );
  }

  const dict = dictionaryResult as Record<string, unknown>;
  const terms = dict.terms as Record<string, unknown>[] | undefined;
  const termEntries = terms || Object.entries(dict)
    .filter(([k]) => k !== 'metadata' && k !== 'generated_at')
    .map(([key, val]) => {
      if (typeof val === 'object' && val !== null) return val as Record<string, unknown>;
      return { term: key, definition: String(val) };
    });

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Generated Dictionary</h3>
      <p className="text-sm text-gray-600">The AI has identified the following terms and definitions from the rule text.</p>

      {termEntries.length > 0 ? (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Term</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Definition / Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {termEntries.map((entry, i) => {
                const e = entry as Record<string, unknown>;
                const term = (e.term as string) || (e.name as string) || (e.key as string) || `Term ${i + 1}`;
                const definition = (e.definition as string) || (e.value as string) || (e.description as string) || JSON.stringify(e);
                const category = e.category as string | undefined;
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 align-top">
                      <span className="font-medium text-gray-900">{term}</span>
                      {category && (
                        <span className="ml-2 inline-flex items-center px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px]">{category}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{definition}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* Fallback: display as key-value cards */
        <div className="grid grid-cols-1 gap-3">
          {Object.entries(dict).map(([key, value]) => (
            <div key={key} className="bg-white border border-gray-200 rounded-lg p-3">
              <span className="text-xs text-gray-500 uppercase tracking-wide">{key.replace(/_/g, ' ')}</span>
              <p className="text-sm text-gray-800 mt-0.5">
                {typeof value === 'string' ? value : JSON.stringify(value)}
              </p>
            </div>
          ))}
        </div>
      )}

      <details className="text-xs">
        <summary className="text-gray-400 cursor-pointer hover:text-gray-600">View raw dictionary data</summary>
        <pre className="bg-gray-50 p-3 rounded-lg mt-2 overflow-auto max-h-48 border border-gray-200 text-gray-600">
          {JSON.stringify(dictionaryResult, null, 2)}
        </pre>
      </details>
    </div>
  );
}
