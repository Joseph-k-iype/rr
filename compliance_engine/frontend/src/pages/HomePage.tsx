import { useRulesNetwork } from '../hooks/useRulesNetwork';
import { RulesNetworkGraph } from '../components/graph/RulesNetworkGraph';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

export function HomePage() {
  const { data, isLoading, error } = useRulesNetwork();

  return (
    <div className="h-full">
      <div className="flex items-baseline justify-between mb-4">
        <h1 className="text-sm font-medium uppercase tracking-widest text-gray-900">Rules Network</h1>
        {data?.stats && (
          <div className="flex gap-6 text-[11px] text-gray-400 tabular-nums">
            <span>{data.stats.total_rules} rules</span>
            <span>{data.stats.total_groups} groups</span>
            <span>{data.stats.total_edges} edges</span>
          </div>
        )}
      </div>

      {isLoading && <LoadingSpinner message="Loading rules network..." />}
      {error && <div className="text-red-600 text-sm p-4 border border-red-200 rounded">Failed to load rules network</div>}
      {data && <RulesNetworkGraph data={data} />}
    </div>
  );
}
