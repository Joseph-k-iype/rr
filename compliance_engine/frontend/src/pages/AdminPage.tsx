import { useState } from 'react';
import { AdminGraph } from '../components/admin/AdminGraph';
import { rebuildGraph } from '../services/adminApi';

export function AdminPage() {
  const [rebuilding, setRebuilding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleRebuild = async () => {
    setRebuilding(true);
    setMessage(null);
    try {
      await rebuildGraph();
      setMessage('Graph rebuilt successfully');
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage('Failed to rebuild graph');
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="h-full">
      <div className="flex items-baseline justify-between mb-4">
        <h1 className="text-sm font-medium uppercase tracking-widest text-gray-900">Admin Panel</h1>
        <div className="flex items-center gap-3">
          {message && (
            <span className={`text-xs ${message.includes('success') ? 'text-green-600' : 'text-red-600'}`}>
              {message}
            </span>
          )}
          <button
            onClick={handleRebuild}
            disabled={rebuilding}
            className="px-3 py-1.5 text-xs text-white bg-gray-900 rounded hover:bg-gray-800 disabled:opacity-50"
          >
            {rebuilding ? 'Rebuilding...' : 'Rebuild Graph'}
          </button>
        </div>
      </div>
      <AdminGraph />
    </div>
  );
}
