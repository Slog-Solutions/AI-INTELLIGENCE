import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import api, { documentApi } from "../services/api";
import Icon, { type IconName } from "../components/Icons";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "../components/Ui";

const chartColors = ["#7f9348", "#c4ad62", "#5f7438", "#d98a32", "#8f987e"];

function numberValue(...values: any[]) {
  const value = values.find((item) => typeof item === "number" && Number.isFinite(item));
  return value ?? 0;
}

function MetricCard({ label, value, caption, icon, tone = "teal" }: { label: string; value: string | number; caption: string; icon: IconName; tone?: string }) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__icon"><Icon name={icon} /></div>
      <div><span>{label}</span><strong>{value}</strong><p>{caption}</p></div>
      <i className="metric-card__line" />
    </article>
  );
}

function ChartPlaceholder({ label }: { label: string }) {
  return (
    <div className="chart-placeholder">
      <div><i style={{ height: "38%" }} /><i style={{ height: "72%" }} /><i style={{ height: "48%" }} /><i style={{ height: "84%" }} /><i style={{ height: "61%" }} /></div>
      <p>{label} · awaiting sufficient source data</p>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadStats = async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await documentApi.getStats();
      setStats(response.data || {});
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadStats(); }, []);

  const categoryData = useMemo(() => Array.isArray(stats?.categories) ? stats.categories : [], [stats]);
  const recentUploads = Array.isArray(stats?.recent_uploads) ? stats.recent_uploads : [];
  const trendData = useMemo(() => Array.isArray(stats?.analytics?.upload_trends) ? stats.analytics.upload_trends : [], [stats]);
  const keywordData = useMemo(() => Array.isArray(stats?.analytics?.keyword_frequency) ? stats.analytics.keyword_frequency : [], [stats]);

  if (loading) return <div className="page page--center"><LoadingState label="Compiling command analytics" /></div>;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Command overview"
        title="Analytics Workspace"
        description="Executive visibility into document ingestion, processing health, and intelligence distribution."
        action={<div className="live-status"><i />Live intelligence picture</div>}
      />
      {error ? <ErrorState message="Unable to retrieve intelligence data." onRetry={loadStats} /> : (
        <>
          <section className="metrics-grid">
            <MetricCard label="Documents uploaded" value={numberValue(stats?.documents_processed, stats?.total_documents)} caption="Indexed intelligence files" icon="document" />
            <MetricCard label="Active Units" value={numberValue(stats?.active_units)} caption="Retrievable knowledge units" icon="library" tone="cyan" />
            <MetricCard label="Intelligence Areas" value={keywordData.length} caption="Key themes extracted" icon="spark" tone="green" />
            <MetricCard label="System alerts" value={numberValue(stats?.ai_alerts)} caption="Items requiring review" icon="alert" tone="amber" />
          </section>

          <section className="analytics-grid">
            <article className="panel chart-panel chart-panel--wide">
              <div className="panel-heading"><div><span className="eyebrow">Ingestion tempo</span><h2>Upload trends</h2></div><span className="chart-period">Last 7 days</span></div>
              <div className="chart-area">
                {trendData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7f9348" stopOpacity={0.4} /><stop offset="100%" stopColor="#7f9348" stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid stroke="#303825" strokeDasharray="4 6" vertical={false} />
                      <XAxis dataKey="date" stroke="#8f987e" tickLine={false} axisLine={false} fontSize={12} />
                      <YAxis stroke="#8f987e" tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                      <Tooltip contentStyle={{ background: "#14190f", border: "1px solid #4a5539", borderRadius: 10 }} />
                      <Area type="monotone" dataKey="uploads" stroke="#9bac63" strokeWidth={2.5} fill="url(#trendFill)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : <ChartPlaceholder label="Upload trend" />}
              </div>
            </article>

            <article className="panel chart-panel">
              <div className="panel-heading"><div><span className="eyebrow">Distribution</span><h2>Documents by category</h2></div></div>
              <div className="donut-layout">
                <div className="donut-chart">
                  {categoryData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart><Pie data={categoryData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={3}>{categoryData.map((entry: any, index: number) => <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip contentStyle={{ background: "#14190f", border: "1px solid #4a5539", borderRadius: 10 }} /></PieChart>
                    </ResponsiveContainer>
                  ) : <div className="donut-empty"><span>0</span><small>No data</small></div>}
                </div>
                <div className="chart-legend">
                  {categoryData.length ? categoryData.slice(0, 5).map((item: any, index: number) => <div key={item.name}><i style={{ background: chartColors[index % chartColors.length] }} /><span>{item.name}</span><strong>{item.value}</strong></div>) : <p>Category data unavailable</p>}
                </div>
              </div>
            </article>

            <article className="panel chart-panel">
              <div className="panel-heading"><div><span className="eyebrow">Key Themes</span><h2>Keyword Frequency</h2></div></div>
              <div className="chart-area chart-area--bar">
                {keywordData.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={keywordData.slice(0, 6)} layout="vertical" margin={{ top: 5, right: 12, left: 12, bottom: 0 }}>
                      <CartesianGrid stroke="#303825" strokeDasharray="4 6" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="name" width={105} stroke="#b1b8a5" axisLine={false} tickLine={false} fontSize={12} />
                      <Tooltip contentStyle={{ background: "#14190f", border: "1px solid #4a5539", borderRadius: 10 }} />
                      <Bar dataKey="value" fill="#c4ad62" radius={[0, 4, 4, 0]} barSize={16} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <ChartPlaceholder label="Keyword frequency" />}
              </div>
            </article>

            <article className="panel recent-panel">
              <div className="panel-heading"><div><span className="eyebrow">Latest intake</span><h2>Recent intelligence</h2></div><Link to="/documents">View library<Icon name="arrow" size={14} /></Link></div>
              {recentUploads.length ? (
                <div className="recent-documents">
                  {recentUploads.slice(0, 5).map((document: any, index: number) => (
                    <div key={document.id || index}>
                      <div className="mini-file"><Icon name="document" size={17} /></div>
                      <div><strong>{document.filename || "Untitled document"}</strong><span>{document.category || "Intelligence file"} · {document.uploaded_at ? new Date(document.uploaded_at).toLocaleDateString() : "Date unavailable"}</span></div>
                      <StatusBadge status={document.status || "Indexed"} />
                    </div>
                  ))}
                </div>
              ) : <EmptyState title="No recent uploads" description="Recently ingested intelligence documents will be listed here." />}
            </article>
          </section>

          <section className="insight-grid">
            <article className="panel insight-card">
              <div className="insight-card__heading"><div className="insight-icon"><Icon name="spark" /></div><div><span className="eyebrow">AI assessment</span><h2>Intelligence Insights</h2></div></div>
              <p className="insight-text">{stats?.analytics?.document_insights || "No insight assessment is available from the current analytics service."}</p>
            </article>
            <article className="panel insight-card insight-card--risk">
              <div className="insight-card__heading"><div className="insight-icon"><Icon name="alert" /></div><div><span className="eyebrow">Command attention</span><h2>Risk indicators</h2></div></div>
              {Array.isArray(stats?.analytics?.risk_indicators) && stats.analytics.risk_indicators.length ? (
                <ul>{stats.analytics.risk_indicators.slice(0, 4).map((risk: any, index: number) => <li key={index}><Icon name="alert" size={14} />{risk.label}</li>)}</ul>
              ) : <p className="muted-copy">No risk indicators are currently supplied by the intelligence service.</p>}
            </article>
          </section>
        </>
      )}
    </div>
  );
}
