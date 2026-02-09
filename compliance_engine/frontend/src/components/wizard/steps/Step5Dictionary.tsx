import { useWizardStore } from '../../../stores/wizardStore';

export function Step5Dictionary() {
  const { dictionaryResult } = useWizardStore();

  if (!dictionaryResult) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Generated Dictionary</h3>
        <div className="border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-sm text-gray-500">No dictionary generated.</p>
          <p className="text-xs text-gray-400 mt-1">Click Next to continue.</p>
        </div>
      </div>
    );
  }

  const dict = dictionaryResult as Record<string, unknown>;
  const dictionaries = dict.dictionaries as Record<string, Record<string, unknown>> | undefined;
  const reasoning = dict.reasoning as string | undefined;
  const coverage = dict.coverage_assessment as string | undefined;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Generated Dictionary</h3>
      <p className="text-sm text-gray-600">Comprehensive terms identified for attribute detection.</p>

      {dictionaries ? (
        Object.entries(dictionaries).map(([categoryName, category]) => {
          const keywords = (category.keywords as string[]) || [];
          const subCategories = category.sub_categories as Record<string, string[]> | undefined;
          const synonyms = category.synonyms as Record<string, string[]> | undefined;
          const acronyms = category.acronyms as Record<string, string> | undefined;
          const description = category.description as string | undefined;
          const confidence = category.confidence as number | undefined;

          return (
            <div key={categoryName} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-gray-900">{categoryName.replace(/_/g, ' ')}</h4>
                  {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
                </div>
                {confidence !== undefined && (
                  <span className="text-xs text-gray-400">{Math.round(confidence * 100)}% confidence</span>
                )}
              </div>

              <div className="p-4 space-y-3">
                {/* Keywords */}
                {keywords.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Keywords ({keywords.length})</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {keywords.map(kw => (
                        <span key={kw} className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">{kw}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sub-categories */}
                {subCategories && Object.keys(subCategories).length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Sub-categories</span>
                    <div className="mt-1 space-y-2">
                      {Object.entries(subCategories).map(([subName, terms]) => (
                        <div key={subName}>
                          <span className="text-xs font-medium text-gray-700">{subName.replace(/_/g, ' ')}</span>
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {terms.map(t => (
                              <span key={t} className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{t}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Acronyms */}
                {acronyms && Object.keys(acronyms).length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Acronyms</span>
                    <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5">
                      {Object.entries(acronyms).map(([acr, full]) => (
                        <div key={acr} className="text-xs">
                          <span className="font-medium text-gray-800">{acr}</span>
                          <span className="text-gray-500"> — {full}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Synonyms */}
                {synonyms && Object.keys(synonyms).length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Synonyms</span>
                    <div className="mt-1 space-y-1">
                      {Object.entries(synonyms).slice(0, 10).map(([term, syns]) => (
                        <div key={term} className="text-xs">
                          <span className="font-medium text-gray-700">{term}</span>
                          <span className="text-gray-400"> = </span>
                          <span className="text-gray-600">{syns.join(', ')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })
      ) : (
        /* Fallback for flat dictionary structure */
        <div className="border border-gray-200 rounded-lg p-4">
          {Object.entries(dict)
            .filter(([k]) => !['internal_patterns', 'reasoning', 'coverage_assessment', 'metadata'].includes(k))
            .map(([key, value]) => (
              <div key={key} className="mb-3 last:mb-0">
                <span className="text-xs text-gray-500 uppercase tracking-wide">{key.replace(/_/g, ' ')}</span>
                <p className="text-sm text-gray-800 mt-0.5">
                  {typeof value === 'string' ? value : Array.isArray(value) ? (value as string[]).join(', ') : JSON.stringify(value)}
                </p>
              </div>
            ))}
        </div>
      )}

      {/* Reasoning & Coverage */}
      {(reasoning || coverage) && (
        <div className="border border-gray-200 rounded-lg p-4 space-y-2">
          {reasoning && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Reasoning</span>
              <p className="text-xs text-gray-700 mt-0.5">{reasoning}</p>
            </div>
          )}
          {coverage && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Coverage Assessment</span>
              <p className="text-xs text-gray-700 mt-0.5">{coverage}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
