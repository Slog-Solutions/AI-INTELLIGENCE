import { Link, useNavigate } from "react-router-dom";
import { clearAuthSession, getAuthUser } from "../services/auth";
import { useEffect, useState } from "react";
import api from "../services/api";

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = getAuthUser();
  const [stats, setStats] = useState<{
    documents_processed: number;
    active_units: number;
    ai_alerts: number;
    categories?: Record<string, number>;
  }>({ documents_processed: 0, active_units: 0, ai_alerts: 0 });

  useEffect(() => {
    if (!user) {
      navigate("/");
    } else {
      api.get("/documents/stats").then(res => setStats(res.data)).catch(console.error);
    }
  }, [navigate, user]);

  const handleLogout = () => {
    clearAuthSession();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">ATIP Executive Dashboard</h1>
          <p className="text-slate-400 mt-2">Offline Defence Training Intelligence and Decision Support</p>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="rounded-2xl bg-slate-900 p-4">
            <div className="text-sm text-slate-400">Role</div>
            <div>{user?.role}</div>
          </div>
          <button onClick={handleLogout} className="rounded-full bg-red-600 px-5 py-3 font-semibold">Logout</button>
        </div>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-2xl bg-slate-900 p-6">
          <div className="text-sm text-slate-400">Documents Processed</div>
          <div className="text-3xl font-bold">{stats.documents_processed}</div>
        </div>
        <div className="rounded-2xl bg-slate-900 p-6">
          <div className="text-sm text-slate-400">Active Units</div>
          <div className="text-3xl font-bold">{stats.active_units}</div>
        </div>
        <div className="rounded-2xl bg-slate-900 p-6">
          <div className="text-sm text-slate-400">AI Alerts</div>
          <div className="text-3xl font-bold text-red-400">{stats.ai_alerts}</div>
        </div>
      </div>
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link to="/upload" className="block rounded-2xl bg-cyan-600 p-6 text-center font-semibold">Upload Center</Link>
        <Link to="/assistant" className="block rounded-2xl bg-slate-800 p-6 text-center font-semibold">AI Assistant</Link>
      </div>
      
      {stats.categories && Object.keys(stats.categories).length > 0 && (
        <div className="mt-8 rounded-2xl bg-slate-900 p-6">
          <h2 className="text-xl font-bold mb-4">Intelligence Distribution</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(stats.categories).map(([cat, count]) => (
              <div key={cat} className="rounded-xl bg-slate-800 p-4 border border-slate-700">
                <div className="text-xs text-slate-400 uppercase tracking-wider">{cat}</div>
                <div className="text-xl font-semibold">{count as number}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
