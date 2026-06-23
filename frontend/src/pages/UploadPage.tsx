import { useRef, useState } from "react";
import api from "../services/api";
import Icon from "../components/Icons";
import { EmptyState, PageHeader, StatusBadge } from "../components/Ui";

function readableDate(value?: string) {
  const date = value ? new Date(value) : new Date();
  return Number.isNaN(date.getTime()) ? "Just now" : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

interface FileWithStatus {
  file: File;
  status: 'idle' | 'uploading' | 'processing' | 'success' | 'error';
  error?: string;
  documentId?: number;
  result?: any;
}

export default function UploadPage() {
  const [files, setFiles] = useState<FileWithStatus[]>([]);
  const [category, setCategory] = useState("Training Report");
  const [source, setSource] = useState("Command HQ");
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [selectedResultIndex, setSelectedResultIndex] = useState<number | null>(null);
  const [tab, setTab] = useState<"preview" | "summary" | "metadata" | "insights">("preview");
  const inputRef = useRef<HTMLInputElement>(null);

  const chooseFiles = (selected?: FileList | null) => {
    if (selected) {
      const newFiles: FileWithStatus[] = Array.from(selected).map(file => ({
        file,
        status: 'idle'
      }));
      setFiles(prev => [...prev, ...newFiles]);
      setError("");
    }
    setDragging(false);
  };

  const uploadAll = async () => {
    const idleFiles = files.filter(f => f.status === 'idle');
    if (idleFiles.length === 0) {
      setError("No new documents to ingest.");
      return;
    }

    setLoading(true);
    setError("");
    
    // Mark as uploading
    setFiles(prev => prev.map(f => f.status === 'idle' ? { ...f, status: 'uploading' } : f));

    const payload = new FormData();
    idleFiles.forEach(f => payload.append("files", f.file));
    payload.append("category", category);
    payload.append("source", source);

    try {
      const response = await api.post("/upload/files", payload);
      const results = response.data.files;
      
      setFiles(prev => prev.map(f => {
        const res = results.find((r: any) => r.filename === f.file.name);
        if (res) {
          return {
            ...f,
            status: res.status === 'processing' ? 'processing' : 'error',
            error: res.error,
            documentId: res.document_id
          };
        }
        return f;
      }));
    } catch (uploadError: any) {
      setError("Intelligence ingestion service encountered an error.");
      setFiles(prev => prev.map(f => f.status === 'uploading' ? { ...f, status: 'error', error: "Upload failed" } : f));
    } finally {
      setLoading(false);
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    if (selectedResultIndex === index) setSelectedResultIndex(null);
  };

  return (
    <div className="page">
      <PageHeader eyebrow="Secure ingestion" title="Upload Center" description="Ingest multiple operational documents concurrently for AI-assisted intelligence retrieval and analytics." />
      <div className="upload-layout">
        <div className="panel upload-console">
          <div className="panel-heading"><div><span className="eyebrow">New intake</span><h2>Document ingestion</h2></div><div className="secure-chip"><Icon name="lock" size={13} />Encrypted</div></div>
          
          <div
            className={`drop-zone ${dragging ? "drop-zone--active" : ""} ${files.length > 0 ? "drop-zone--selected" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); chooseFiles(event.dataTransfer.files); }}
          >
            <input ref={inputRef} type="file" multiple hidden onChange={(event) => chooseFiles(event.target.files)} />
            <div className="drop-zone__icon"><Icon name={files.length > 0 ? "check" : "upload"} size={25} /></div>
            {files.length > 0 ? (
              <><h3>{files.length} documents selected</h3><p>Ready for secure ingestion</p><button type="button" onClick={(event) => { event.stopPropagation(); setFiles([]); }}>Clear all</button></>
            ) : (
              <><h3>Drop intelligence documents here</h3><p>or click to browse the secure workstation</p><span>PDF, DOCX, TXT, CSV, XLSX</span></>
            )}
          </div>

          <div className="form-grid">
            <label><span className="field-label">Intelligence category</span><div className="select-shell select-shell--full"><select value={category} onChange={(event) => setCategory(event.target.value)}><option>Training Report</option><option>After Action Review</option><option>Intelligence Brief</option><option>Logistics Report</option><option>Field Manual</option></select><Icon name="chevron" size={14} /></div></label>
            <label><span className="field-label">Origin / source</span><div className="input-shell"><Icon name="shield" size={16} /><input value={source} onChange={(event) => setSource(event.target.value)} placeholder="Command HQ" /></div></label>
          </div>

          {error && <div className="form-error"><Icon name="alert" size={17} />{error}</div>}
          
          <button className="button button--primary upload-submit" onClick={uploadAll} disabled={loading || !files.some(f => f.status === 'idle')}>
            {loading ? <><span className="button-spinner" />Processing batch</> : <><Icon name="upload" />Ingest all documents</>}
          </button>

          {files.length > 0 && (
            <div className="file-list-status">
              <span className="eyebrow">Queue status</span>
              <div className="file-status-grid">
                {files.map((f, i) => (
                  <div key={i} className={`file-status-item ${f.status}`}>
                    <Icon name="document" size={14} />
                    <span className="file-name">{f.file.name}</span>
                    <span className="status-label">{f.status}</span>
                    {f.status === 'idle' && <button onClick={() => removeFile(i)}><Icon name="close" size={12} /></button>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <section className="upload-result">
          <div className="panel upload-awaiting">
            <div className="upload-awaiting__visual"><Icon name="analytics" size={34} /><span /><span /><span /></div>
            <h2>Multi-file Processing</h2>
            <p>Documents are processed in the background. You can track their status in the queue and view them in the Library once complete.</p>
            <div className="awaiting-features">
              <span><Icon name="check" />Concurrent Ingestion</span>
              <span><Icon name="spark" />Background Analysis</span>
              <span><Icon name="analytics" />Auto-Analytics</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
