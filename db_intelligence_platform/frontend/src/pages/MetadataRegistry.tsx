import React, { useEffect, useState } from 'react';
import { Database, Activity, Trash2, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

interface DatabaseMeta {
  id: string;
  name: string;
  status: string;
}

interface StatsResponse {
  total_databases: number;
  databases: DatabaseMeta[];
  entities_identified: number;
}

const MetadataRegistry: React.FC = () => {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/stats');
      if (!response.ok) throw new Error('Failed to fetch');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch registry stats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this database schema? This action cannot be undone.')) {
      return;
    }
    
    setDeletingId(id);
    try {
      await fetch(`http://localhost:8000/api/v1/onboard/${id}`, { method: 'DELETE' });
      await fetchStats();
    } catch (error) {
      console.error('Failed to delete database:', error);
      alert('Failed to delete database. Please check the logs.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-7xl mx-auto pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center">
            <Database className="w-8 h-8 mr-3 text-emerald-400" />
            Metadata Registry
          </h1>
          <p className="mt-2 text-slate-400">Manage your connected data sources and their knowledge graphs.</p>
        </div>
      </div>

      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden backdrop-blur-xl">
        <div className="p-6 border-b border-slate-700/50 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-white">Connected Databases</h2>
          <div className="text-sm text-slate-400">
            Total Entities Extracted: <span className="text-emerald-400 font-bold">{stats?.entities_identified || 0}</span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin mb-4 text-emerald-400" />
            <p>Loading registry data...</p>
          </div>
        ) : stats?.databases && stats.databases.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900/50 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-4 font-semibold">Database Name</th>
                  <th className="px-6 py-4 font-semibold">Connection ID</th>
                  <th className="px-6 py-4 font-semibold">Status</th>
                  <th className="px-6 py-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {stats.databases.map((db) => (
                  <tr key={db.id} className="hover:bg-slate-700/20 transition-colors duration-150">
                    <td className="px-6 py-4 whitespace-nowrap font-medium text-white flex items-center">
                      <Database className="w-4 h-4 mr-2 text-slate-400" />
                      {db.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-slate-500">
                      {db.id.substring(0, 8)}...{db.id.substring(db.id.length - 4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {db.status === 'completed' ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Online
                        </span>
                      ) : db.status === 'running' ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          <Activity className="w-3 h-3 mr-1 animate-pulse" />
                          Onboarding...
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          <XCircle className="w-3 h-3 mr-1" />
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <button
                        onClick={() => handleDelete(db.id)}
                        disabled={deletingId === db.id}
                        className={`inline-flex items-center p-2 rounded-lg transition-colors ${
                          deletingId === db.id 
                            ? 'text-slate-500 bg-slate-800 cursor-not-allowed'
                            : 'text-rose-400 hover:text-white hover:bg-rose-500/20'
                        }`}
                        title="Delete Database"
                      >
                        {deletingId === db.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400">
            <Database className="w-12 h-12 mx-auto mb-4 text-slate-600 opacity-50" />
            <p className="text-lg font-medium text-slate-300">No databases connected</p>
            <p className="mt-1">Navigate to the Admin section to onboard a new database.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetadataRegistry;
