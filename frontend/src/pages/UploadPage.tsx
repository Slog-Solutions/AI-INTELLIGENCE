import { useRef, useState } from "react";
import api from "../services/api";
import Icon from "../components/Icons";
import { EmptyState, PageHeader, StatusBadge } from "../components/Ui";

function readableDate(value?: string) {
  const date = value ? new Date(value) : new Date();
  return Number.isNaN(date.getTime()) ? "Just now" : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function Preview({ preview }: { preview: any }) {
  if (!preview?.data) return <EmptyState title="Preview unavailable" description="No compatible preview was returned for this file type." />;
  if (preview.type === "csv" || preview.type === "excel") {
    const rows = preview.type === "csv" ? preview.data : Object.values(preview.data || {})[0] as any[];
    if (!Array.isArray(rows) || !rows.length) return <EmptyState title="No data rows" description="The uploaded file contains no displayable records." />;
    const headers = Object.keys(rows[0]);
    return <div className="data-table-wrap"><table className="data-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.slice(0, 8).map((row, index) => <tr key={index}>{headers.map((header) => <td key={header}>{String(row[header] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
  }
  return <div className="text-preview">{typeof preview.data === "string" ? preview.data : "Preview data is not available in a readable format."}</div>;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("Training Report");
  const [source, setSource] = useState("Command HQ");
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"preview" | "summary" | "metadata" | "insights">("preview");
  const inputRef = useRef<HTMLInputElement>(null);

  const chooseFile = (selected?: File) => {
    if (selected) {
      setFile(selected);
      setError("");
    }
    setDragging(false);
  };

  const upload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError("Select an intelligence document before beginning ingestion.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    const payload = new FormData();
    payload.append("file", file);
    payload.append("category", category);
    payload.append("source", source);
    try {
      const response = await api.post("/upload/file", payload);
      setResult(response.data);
      setTab("preview");
    } catch (uploadError: any) {
      const detail = uploadError.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Intelligence ingestion service temporarily unavailable.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <PageHeader eyebrow="Secure ingestion" title="Upload Center" description="Ingest, classify, preview, and prepare operational documents for AI-assisted intelligence retrieval." />
      <div className="upload-layout">
        <form className="panel upload-console" onSubmit={upload}>
          <div className="panel-heading"><div><span className="eyebrow">New intake</span><h2>Document ingestion</h2></div><div className="secure-chip"><Icon name="lock" size={13} />Encrypted</div></div>
          <div
            className={`drop-zone ${dragging ? "drop-zone--active" : ""} ${file ? "drop-zone--selected" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }}
          >
            <input ref={inputRef} type="file" hidden onChange={(event) => chooseFile(event.target.files?.[0])} />
            <div className="drop-zone__icon"><Icon name={file ? "check" : "upload"} size={25} /></div>
            {file ? <><h3>{file.name}</h3><p>{(file.size / 1024 / 1024).toFixed(2)} MB · Ready for secure ingestion</p><button type="button" onClick={(event) => { event.stopPropagation(); setFile(null); }}>Choose another file</button></> : <><h3>Drop intelligence document here</h3><p>or click to browse the secure workstation</p><span>PDF, DOCX, TXT, CSV, XLSX</span></>}
          </div>
          <div className="form-grid">
            <label><span className="field-label">Intelligence category</span><div className="select-shell select-shell--full"><select value={category} onChange={(event) => setCategory(event.target.value)}><option>Training Report</option><option>After Action Review</option><option>Intelligence Brief</option><option>Logistics Report</option></select><Icon name="chevron" size={14} /></div></label>
            <label><span className="field-label">Origin / source</span><div className="input-shell"><Icon name="shield" size={16} /><input value={source} onChange={(event) => setSource(event.target.value)} placeholder="Command HQ" /></div></label>
          </div>
          {error && <div className="form-error"><Icon name="alert" size={17} />{error}</div>}
          <button className="button button--primary upload-submit" disabled={loading}>{loading ? <><span className="button-spinner" />Processing intelligence</> : <><Icon name="upload" />Upload and analyze</>}</button>
          <div className="ingestion-steps"><span className="active"><i>1</i>Upload</span><b /><span className={loading || result ? "active" : ""}><i>2</i>Extract</span><b /><span className={result ? "active" : ""}><i>3</i>Index</span><b /><span className={result ? "active" : ""}><i>4</i>Ready</span></div>
        </form>

        <section className="upload-result">
          {!result ? (
            <div className="panel upload-awaiting">
              <div className="upload-awaiting__visual"><Icon name="document" size={34} /><span /><span /><span /></div>
              <h2>Awaiting intelligence package</h2>
              <p>After ingestion, document preview, available AI analysis, metadata, and intelligence insights will appear here.</p>
              <div className="awaiting-features"><span><Icon name="eye" />Preview</span><span><Icon name="spark" />AI summary</span><span><Icon name="clipboard" />Metadata</span><span><Icon name="analytics" />Insights</span></div>
            </div>
          ) : (
            <div className="result-stack">
              <article className="panel ingestion-card">
                <div className="ingestion-card__icon"><Icon name="document" size={24} /><span>{String(result.filename || file?.name).split(".").pop()?.toUpperCase()}</span></div>
                <div className="ingestion-card__name"><span className="eyebrow">Ingestion complete</span><h2>{result.filename || file?.name}</h2><p>{result.source || source}</p></div>
                <StatusBadge status={result.status || "Processed"} />
                <div className="ingestion-card__metrics">
                  <div><span>Pages</span><strong>{result.pages ?? result.page_count ?? "—"}</strong></div>
                  <div><span>Chunks</span><strong>{result.chunks ?? result.chunk_count ?? "—"}</strong></div>
                  <div><span>Category</span><strong>{result.category || category}</strong></div>
                  <div><span>Uploaded</span><strong>{readableDate(result.uploaded_at)}</strong></div>
                </div>
              </article>
              <article className="panel result-detail">
                <div className="result-tabs">
                  {(["preview", "summary", "metadata", "insights"] as const).map((item) => <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item === "summary" ? "AI Summary" : item === "insights" ? "Intelligence Insights" : item.charAt(0).toUpperCase() + item.slice(1)}</button>)}
                </div>
                <div className="result-detail__content">
                  {tab === "preview" && <Preview preview={result.preview} />}
                  {tab === "summary" && (result.summary ? <div className="summary-copy">{result.summary}</div> : <EmptyState icon="spark" title="Summary not provided" description="The document was processed successfully, but the current intelligence service did not return an AI summary." />)}
                  {tab === "metadata" && <div className="metadata-grid"><div><span>Filename</span><strong>{result.filename || file?.name}</strong></div><div><span>File type</span><strong>{String(result.filename || file?.name).split(".").pop()?.toUpperCase()}</strong></div><div><span>Category</span><strong>{result.category || category}</strong></div><div><span>Source</span><strong>{result.source || source}</strong></div><div><span>Page count</span><strong>{result.pages ?? result.page_count ?? "Not supplied"}</strong></div><div><span>Chunk count</span><strong>{result.chunks ?? result.chunk_count ?? "Not supplied"}</strong></div></div>}
                  {tab === "insights" && <EmptyState icon="analytics" title="Insights pending" description="No structured intelligence insights were supplied by the current API for this document." />}
                </div>
              </article>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
