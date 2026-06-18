import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("Training Report");
  const [source, setSource] = useState("Command HQ");
  const [loading, setLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [error, setError] = useState("");

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError("");
    setUploadResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", category);
    formData.append("source", source);

    try {
      const res = await api.post("/upload/file", formData);
      setUploadResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const renderPreview = (preview: any) => {
    if (!preview) return null;
    if (preview.type === "csv" || preview.type === "excel") {
      const data = preview.type === "csv" ? preview.data : Object.values(preview.data)[0] as any[];
      if (!data || data.length === 0) return <p>No data available</p>;
      const headers = Object.keys(data[0]);
      return (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="bg-slate-800">
                {headers.map(h => <th key={h} className="p-2 border border-slate-700">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 5).map((row, i) => (
                <tr key={i} className="border-b border-slate-800">
                  {headers.map(h => <td key={h} className="p-2 border border-slate-700">{row[h]}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 5 && <p className="text-xs text-slate-500 mt-2">Showing first 5 rows...</p>}
        </div>
      );
    }
    return <pre className="whitespace-pre-wrap text-xs bg-slate-950 p-4 rounded border border-slate-800">{preview.data}</pre>;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <button onClick={() => navigate("/dashboard")} className="mb-6 text-cyan-400 hover:underline">← Back to Dashboard</button>
        <h1 className="text-3xl font-bold mb-8">Intelligence Upload Center</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1">
            <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
              <h2 className="text-xl font-semibold mb-4">New Document</h2>
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Intelligence File</label>
                  <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="w-full bg-slate-800 p-2 rounded border border-slate-700" required />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full bg-slate-800 p-2 rounded border border-slate-700">
                    <option>Training Report</option>
                    <option>After Action Review</option>
                    <option>Intelligence Brief</option>
                    <option>Logistics Report</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Source</label>
                  <input type="text" value={source} onChange={(e) => setSource(e.target.value)} className="w-full bg-slate-800 p-2 rounded border border-slate-700" />
                </div>
                <button disabled={loading} className="w-full bg-cyan-600 hover:bg-cyan-500 py-3 rounded-xl font-bold transition-colors disabled:opacity-50">
                  {loading ? "Processing Intelligence..." : "Upload & Analyze"}
                </button>
              </form>
              {error && <p className="mt-4 text-red-400 text-sm bg-red-400/10 p-3 rounded-lg border border-red-400/20">{error}</p>}
            </div>
          </div>

          <div className="lg:col-span-2">
            {uploadResult ? (
              <div className="space-y-6 animate-in fade-in duration-500">
                <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h2 className="text-2xl font-bold">{uploadResult.filename}</h2>
                      <p className="text-slate-400">{uploadResult.category} | {uploadResult.source}</p>
                    </div>
                    <span className="bg-green-500/20 text-green-400 px-3 py-1 rounded-full text-xs font-bold uppercase">Processed</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
                    <div className="bg-slate-800 p-3 rounded-xl border border-slate-700">
                      <div className="text-xs text-slate-500">Type</div>
                      <div className="font-semibold">{uploadResult.filename.split('.').pop().toUpperCase()}</div>
                    </div>
                    <div className="bg-slate-800 p-3 rounded-xl border border-slate-700">
                      <div className="text-xs text-slate-500">Uploaded</div>
                      <div className="font-semibold">{new Date(uploadResult.uploaded_at).toLocaleTimeString()}</div>
                    </div>
                    <div className="bg-slate-800 p-3 rounded-xl border border-slate-700">
                      <div className="text-xs text-slate-500">Status</div>
                      <div className="font-semibold text-green-400">Ready</div>
                    </div>
                    <div className="bg-slate-800 p-3 rounded-xl border border-slate-700">
                      <div className="text-xs text-slate-500">RAG</div>
                      <div className="font-semibold text-cyan-400">Indexed</div>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
                  <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <span className="text-cyan-400">✦</span> AI Intelligence Summary
                  </h3>
                  <div className="prose prose-invert max-w-none text-slate-300 whitespace-pre-wrap bg-slate-950/50 p-4 rounded-xl border border-slate-800">
                    {uploadResult.summary || "Generating summary..."}
                  </div>
                </div>

                <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
                  <h3 className="text-lg font-bold mb-4">Document Preview</h3>
                  {renderPreview(uploadResult.preview)}
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 bg-slate-900/50 rounded-2xl border border-dashed border-slate-800 p-12">
                <div className="text-6xl mb-4">📄</div>
                <p className="text-lg">Upload a document to see AI analysis and preview</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
