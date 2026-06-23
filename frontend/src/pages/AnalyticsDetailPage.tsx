import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { documentApi, DocumentOut } from "../services/api";
import Icon from "../components/Icons";
import { PageHeader, StatusBadge, EmptyState } from "../components/Ui";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend
} from "recharts";

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8"];

export default function AnalyticsDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) loadDocument(parseInt(id));
  }, [id]);

  const loadDocument = async (docId: number) => {
    try {
      const response = await documentApi.getDocument(docId);
      setDocument(response.data);
    } catch (error) {
      console.error("Failed to load document", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="page-loading">Analyzing intelligence...</div>;
  if (!document) return <EmptyState title="Document not found" description="The requested document could not be retrieved from the library." />;

  const analytics = document.analytics;

  return (
    <div className="page analytics-detail">
      <button className="back-link" onClick={() => navigate(-1)}>
        <Icon name="chevron" size={14} /> Back to library
      </button>
      
      <PageHeader 
        eyebrow="Intelligence Analysis" 
        title={document.filename} 
        description={`Detailed analytics and AI-extracted insights for ${document.category}.`}
      />

      <div className="analytics-grid">
        <section className="panel doc-summary-panel">
          <div className="panel-heading"><h2>Document Assessment</h2><StatusBadge status={document.status} /></div>
          <div className="summary-content">
            <p>{document.summary || "No AI summary available for this document."}</p>
          </div>
          <div className="meta-info-grid">
            <div><span>Source</span><strong>{document.source}</strong></div>
            <div><span>Pages</span><strong>{document.page_count || "—"}</strong></div>
            <div><span>Chunks</span><strong>{document.chunk_count || "—"}</strong></div>
            <div><span>Ingested</span><strong>{new Date(document.uploaded_at).toLocaleDateString()}</strong></div>
          </div>
        </section>

        {!analytics ? (
          <div className="panel col-span-2">
            <EmptyState icon="analytics" title="No analytics data" description="This document does not have structured analytics data. It might still be processing or is a text-only document." />
          </div>
        ) : (
          <>
            {analytics.type === "tabular" ? (
              <>
                <div className="panel col-span-2">
                  <div className="panel-heading"><h2>Data Distributions</h2></div>
                  <div className="charts-container">
                    {analytics.charts?.map((chart: any) => (
                      <div key={chart.id} className="chart-wrapper">
                        <h3>{chart.title}</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            {chart.type === "bar" ? (
                              <BarChart data={chart.data}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis />
                                <Tooltip />
                                <Bar dataKey="value" fill="#3b82f6" />
                              </BarChart>
                            ) : (
                              <PieChart>
                                <Pie data={chart.data} cx="50%" cy="50%" outerRadius={80} fill="#8884d8" dataKey="value" label>
                                  {chart.data.map((_: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                  ))}
                                </Pie>
                                <Tooltip />
                              </PieChart>
                            )}
                          </ResponsiveContainer>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="panel">
                  <div className="panel-heading"><h2>Extracted Entities</h2></div>
                  <div className="tag-cloud">
                    {analytics.entities?.map((e: string, i: number) => <span key={i} className="entity-tag">{e}</span>)}
                    {analytics.keywords?.map((k: string, i: number) => <span key={i} className="keyword-tag">{k}</span>)}
                  </div>
                </div>
                <div className="panel">
                  <div className="panel-heading"><h2>Identified Risks</h2></div>
                  <ul className="risk-list">
                    {analytics.risks?.map((r: string, i: number) => (
                      <li key={i} className="risk-item">
                        <Icon name="alert" size={16} />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="panel col-span-2">
                  <div className="panel-heading"><h2>Topic Breakdown</h2></div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={analytics.charts?.[0]?.data || []}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="value" fill="#10b981" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
