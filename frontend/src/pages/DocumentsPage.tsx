import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

export default function DocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [viewMode, setViewMode] = useState<"list" | "preview" | "summary">("list");

  const fetchDocuments = async () => {
    try {
      const res = await api.get("/documents/list");
      setDocuments(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this intelligence document?")) return;
    try {
      await api.delete(`/documents/${id}`);
      setDocuments(prev => prev.filter(d => d.id !== id));
      if (selectedDoc?.id === id) setSelectedDoc(null);
    } catch (err) {
      alert("Delete failed");
    }
  };

  const renderPreview = (preview: any) => {
    if (!preview) return <p>No preview available.</p>;
    if (preview.type === "csv" || preview.type === "excel") {
      const data = preview.type === "csv" ? preview.data : Object.values(preview.data)[0] as any[];
      if (!data || data.length === 0) return <p>No data available</p>;
      const headers = Object.keys(data[0]);
      return (
        <div className="overflow-auto max-h-[60vh]">
          <table className="w-full text-left text-sm border-collapse">
            <thead className="sticky top-0 bg-slate-800">
              <tr>
                {headers.map(h => <th key={h} className="p-2 border border-slate-700">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={i} className="border-b border-slate-800">
                  {headers.map(h => <td key={h} className="p-2 border border-slate-700">{row[h]}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return <pre className="whitespace-pre-wrap text-sm bg-slate-950 p-6 rounded-xl border border-slate-800">{preview.data}</pre>;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8">
          <div>
            <button onClick={() => navigate("/dashboard")} className="text-cyan-400 hover:underline mb-2 block">← Dashboard</button>
            <h1 className="text-3xl font-bold">Intelligence Repository</h1>
          </div>
          <button onClick={() => navigate("/upload")} className="bg-cyan-600 hover:bg-cyan-500 px-6 py-3 rounded-xl font-bold">Upload New</button>
        </header>

        {loading ? (
          <div className="flex justify-center p-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 space-y-4 overflow-y-auto max-h-[80vh] pr-2">
              {documents.map(doc => (
                <div 
                  key={doc.id} 
                  onClick={() => { setSelectedDoc(doc); setViewMode("preview"); }}
                  className={`p-4 rounded-2xl border cursor-pointer transition-all ${selectedDoc?.id === doc.id ? 'bg-slate-800 border-cyan-500 shadow-lg shadow-cyan-500/10' : 'bg-slate-900 border-slate-800 hover:border-slate-700'}`}
                >
                  <div className="flex justify-between items-start">
                    <h3 className="font-bold truncate pr-4">{doc.filename}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-bold ${doc.status === 'processed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                      {doc.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{doc.category} • {doc.source}</p>
                  <div className="flex gap-2 mt-4">
                    <button onClick={(e) => { e.stopPropagation(); setSelectedDoc(doc); setViewMode("preview"); }} className="text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded border border-slate-700">Preview</button>
                    <button onClick={(e) => { e.stopPropagation(); setSelectedDoc(doc); setViewMode("summary"); }} className="text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded border border-slate-700">Summary</button>
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }} className="text-[10px] bg-red-900/20 hover:bg-red-900/40 text-red-400 px-2 py-1 rounded border border-red-900/30 ml-auto">Delete</button>
                  </div>
                </div>
              ))}
              {documents.length === 0 && <p className="text-slate-500 text-center py-10">No documents found.</p>}
            </div>

            <div className="lg:col-span-2">
              {selectedDoc ? (
                <div className="bg-slate-900 rounded-2xl border border-slate-800 p-8 h-full min-h-[60vh]">
                  <div className="flex justify-between items-center mb-6 border-b border-slate-800 pb-4">
                    <div>
                      <h2 className="text-2xl font-bold">{selectedDoc.filename}</h2>
                      <p className="text-slate-400">{selectedDoc.category} | Source: {selectedDoc.source}</p>
                    </div>
                    <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800">
                      <button 
                        onClick={() => setViewMode("preview")} 
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${viewMode === "preview" ? "bg-slate-800 text-cyan-400 shadow-sm" : "text-slate-500 hover:text-slate-300"}`}
                      >
                        Preview
                      </button>
                      <button 
                        onClick={() => setViewMode("summary")} 
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${viewMode === "summary" ? "bg-slate-800 text-cyan-400 shadow-sm" : "text-slate-500 hover:text-slate-300"}`}
                      >
                        AI Summary
                      </button>
                    </div>
                  </div>

                  <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                    {viewMode === "summary" ? (
                      <div className="prose prose-invert max-w-none">
                        <div className="bg-slate-950/50 p-6 rounded-2xl border border-slate-800 text-slate-300 whitespace-pre-wrap leading-relaxed">
                          {selectedDoc.summary || "No summary available for this document."}
                        </div>
                      </div>
                    ) : (
                      renderPreview(selectedDoc.preview)
                    )}
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 bg-slate-900/30 rounded-2xl border border-dashed border-slate-800 p-12">
                  <div className="text-6xl mb-4">🔍</div>
                  <p className="text-lg">Select a document to view details</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
