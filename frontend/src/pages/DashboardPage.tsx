import { Link, useNavigate } from "react-router-dom";
import { clearAuthSession, getAuthUser } from "../services/auth";
import { useEffect, useState } from "react";
import api from "../services/api";

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = getAuthUser();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      navigate("/");
    } else {
      api.get("/documents/stats")
        .then(res => setStats(res.data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [navigate, user]);

  const handleLogout = () => {
    clearAuthSession();
    navigate("/");
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500"></div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <header className="mb-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="bg-cyan-600 p-1.5 rounded-lg text-xs font-bold">ATIP</span>
            <h1 className="text-3xl font-bold tracking-tight">Intelligence Dashboard</h1>
          </div>
          <p className="text-slate-400">Secure Defence Training Analysis & Strategic Decision Support</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-sm font-bold">{user?.full_name || user?.username}</div>
            <div className="text-xs text-slate-500 uppercase">{user?.role}</div>
          </div>
          <button onClick={handleLogout} className="bg-slate-900 hover:bg-red-900/40 text-slate-400 hover:text-red-400 p-3 rounded-xl border border-slate-800 transition-all">
            Logout
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 relative overflow-hidden group">
          <div className="text-sm text-slate-500 font-bold uppercase mb-1">Total Intelligence</div>
          <div className="text-4xl font-black">{stats?.documents_processed}</div>
          <div className="text-xs text-slate-400 mt-2">Documents indexed</div>
          <div className="absolute -right-2 -bottom-2 text-6xl opacity-5 group-hover:opacity-10 transition-opacity">📄</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 relative overflow-hidden group">
          <div className="text-sm text-slate-500 font-bold uppercase mb-1">Active Units</div>
          <div className="text-4xl font-black">{stats?.active_units}</div>
          <div className="text-xs text-slate-400 mt-2">Under monitoring</div>
          <div className="absolute -right-2 -bottom-2 text-6xl opacity-5 group-hover:opacity-10 transition-opacity">🎖️</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 relative overflow-hidden group">
          <div className="text-sm text-slate-500 font-bold uppercase mb-1">System Alerts</div>
          <div className="text-4xl font-black text-red-500">{stats?.ai_alerts}</div>
          <div className="text-xs text-slate-400 mt-2">Anomalies detected</div>
          <div className="absolute -right-2 -bottom-2 text-6xl opacity-5 group-hover:opacity-10 transition-opacity">⚠️</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 relative overflow-hidden group">
          <div className="text-sm text-slate-500 font-bold uppercase mb-1">Readiness Score</div>
          <div className="text-4xl font-black text-cyan-500">{stats?.analytics?.readiness_score}%</div>
          <div className="text-xs text-slate-400 mt-2">Overall combat status</div>
          <div className="absolute -right-2 -bottom-2 text-6xl opacity-5 group-hover:opacity-10 transition-opacity">⚡</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
              <span className="text-cyan-500">✦</span> AI Intelligence Insights
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="text-xs font-bold text-slate-500 uppercase mb-3">Key Trends</div>
                <ul className="space-y-2">
                  {stats?.analytics?.trends.map((t: string, i: number) => (
                    <li key={i} className="text-sm flex gap-2">
                      <span className="text-cyan-500">↗</span> {t}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="text-xs font-bold text-slate-500 uppercase mb-3">Risk Indicators</div>
                <ul className="space-y-2">
                  {stats?.analytics?.risk_indicators.map((r: string, i: number) => (
                    <li key={i} className="text-sm flex gap-2">
                      <span className="text-red-500">!</span> {r}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">Recent Intelligence</h2>
              <Link to="/documents" className="text-sm text-cyan-400 hover:underline">View All</Link>
            </div>
            <div className="space-y-3">
              {stats?.recent_uploads.map((doc: any, i: number) => (
                <div key={i} className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex justify-between items-center">
                  <div>
                    <div className="font-bold text-sm">{doc.filename}</div>
                    <div className="text-xs text-slate-500">{new Date(doc.uploaded_at).toLocaleDateString()}</div>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-bold ${doc.status === 'processed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
            <h2 className="text-xl font-bold mb-6">Quick Actions</h2>
            <div className="space-y-3">
              <Link to="/upload" className="block w-full bg-cyan-600 hover:bg-cyan-500 p-4 rounded-xl text-center font-bold transition-all">
                Upload Intelligence
              </Link>
              <Link to="/assistant" className="block w-full bg-slate-800 hover:bg-slate-700 p-4 rounded-xl text-center font-bold border border-slate-700 transition-all">
                Launch AI Assistant
              </Link>
              <Link to="/documents" className="block w-full bg-slate-800 hover:bg-slate-700 p-4 rounded-xl text-center font-bold border border-slate-700 transition-all">
                Document Repository
              </Link>
            </div>
          </div>

          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
            <h2 className="text-xl font-bold mb-6">Intelligence Distribution</h2>
            <div className="space-y-4">
              {Object.entries(stats?.categories || {}).map(([cat, count]: [string, any]) => (
                <div key={cat}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{cat}</span>
                    <span className="font-bold">{count}</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-950 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-cyan-500 rounded-full" 
                      style={{ width: `${(count / stats.documents_processed) * 100}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
