import { Link, useNavigate } from "react-router-dom";
import { clearAuthSession, getAuthUser } from "../services/auth";
import { useEffect } from "react";

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = getAuthUser();

  useEffect(() => {
    if (!user) {
      navigate("/");
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
        <div className="rounded-2xl bg-slate-900 p-6">Documents Processed<br />0</div>
        <div className="rounded-2xl bg-slate-900 p-6">Active Units<br />0</div>
        <div className="rounded-2xl bg-slate-900 p-6">AI Alerts<br />0</div>
      </div>
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link to="/upload" className="block rounded-2xl bg-cyan-600 p-6 text-center font-semibold">Upload Center</Link>
        <Link to="/assistant" className="block rounded-2xl bg-slate-800 p-6 text-center font-semibold">AI Assistant</Link>
      </div>
    </div>
  );
}
