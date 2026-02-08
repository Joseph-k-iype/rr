import { useRulesNetwork } from '../hooks/useRulesNetwork';
import { RulesNetworkGraph } from '../components/graph/RulesNetworkGraph';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

export function HomePage() {
  const { data, isLoading, error } = useRulesNetwork();

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Rules Network</h1>
        {data?.stats && (
          <div className="flex gap-4 text-sm text-gray-500">
            <span>{data.stats.total_rules} rules</span>
            <span>{data.stats.total_groups} groups</span>
            <span>{data.stats.total_edges} connections</span>
          </div>
        )}
      </div>

      {isLoading && <LoadingSpinner message="Loading rules network..." />}
      {error && <div className="text-red-600 p-4 bg-red-50 rounded-lg">Failed to load rules network</div>}
      {data && <RulesNetworkGraph data={data} />}
    </div>
  );
}
