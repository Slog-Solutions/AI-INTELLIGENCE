import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { getAuthToken } from "../services/auth";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("Training Reports");
  const [source, setSource] = useState("Unit Upload");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!getAuthToken()) {
      navigate("/");
    }
  }, [navigate]);

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      setMessage("Select a file first.");
      return;
    }
    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", category);
    formData.append("source", source);

    try {
      await api.post("/upload/file", formData);
      setMessage("Upload successful.");
    } catch (err) {
      setMessage("Upload failed.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <div className="max-w-3xl mx-auto rounded-3xl bg-slate-900 p-8 shadow-xl">
        <h2 className="text-2xl font-bold mb-4">Document Upload Center</h2>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-sm font-medium">File</label>
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-2 w-full text-slate-200" />
          </div>
          <div>
            <label className="block text-sm font-medium">Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-2 w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2">
              <option>Training Reports</option>
              <option>Performance Records</option>
              <option>Attendance Sheets</option>
              <option>Medical Records</option>
              <option>Ration Logs</option>
              <option>Fuel Logs</option>
              <option>Equipment Logs</option>
              <option>SOP Documents</option>
              <option>War Reports</option>
              <option>Intelligence Reports</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium">Source</label>
            <input type="text" value={source} onChange={(e) => setSource(e.target.value)} className="mt-2 w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2" />
          </div>
          <button className="rounded-full bg-cyan-600 px-5 py-3 font-semibold">Upload</button>
        </form>
        {message && <p className="mt-4 text-cyan-200">{message}</p>}
      </div>
    </div>
  );
}
