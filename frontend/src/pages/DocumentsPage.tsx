import { useEffect, useState } from "react";
import api from "../services/api";

interface DocumentItem {
  id: number;
  filename: string;
  category: string;
  source: string;
  metadata: string | null;
  uploaded_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);

  useEffect(() => {
    api.get("/documents/list").then((response) => {
      setDocuments(response.data);
    });
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <h1 className="text-3xl font-bold">Documents</h1>
      <div className="mt-6 grid gap-4">
        {documents.map((doc) => (
          <div key={doc.id} className="rounded-3xl bg-slate-900 p-6">
            <div className="text-xl font-semibold">{doc.filename}</div>
            <div className="text-slate-400">Category: {doc.category}</div>
            <div className="text-slate-400">Source: {doc.source}</div>
            <div className="text-slate-400">Uploaded at: {new Date(doc.uploaded_at).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
