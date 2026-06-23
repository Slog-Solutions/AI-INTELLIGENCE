import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Icon from "../components/Icons";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "../components/Ui";

type ViewMode = "grid" | "list";
type SortMode = "newest" | "oldest" | "name";

function safeDate(value?: string) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

function Preview({ preview }: { preview: any }) {
  if (!preview?.data) return <EmptyState title="Preview unavailable" description="This document has no compatible preview data." />;
  if (preview.type === "csv" || preview.type === "excel") {
    const rows = preview.type === "csv" ? preview.data : Object.values(preview.data || {})[0] as any[];
    if (!Array.isArray(rows) || !rows.length) return <EmptyState title="No preview rows" description="The file was processed but contains no displayable rows." />;
    const headers = Object.keys(rows[0]);
    return (
      <div className="data-table-wrap">
        <table className="data-table">
          <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
          <tbody>{rows.slice(0, 15).map((row, index) => <tr key={index}>{headers.map((header) => <td key={header}>{String(row[header] ?? "—")}</td>)}</tr>)}</tbody>
        </table>
      </div>
    );
  }
  return <div className="text-preview">{typeof preview.data === "string" ? preview.data : "Preview data is not available in a readable format."}</div>;
}

export default function DocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState<SortMode>("newest");
  const [view, setView] = useState<ViewMode>("grid");
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [detailTab, setDetailTab] = useState<"preview" | "summary">("preview");

  const fetchDocuments = async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await api.get("/documents/list");
      setDocuments(Array.isArray(response.data) ? response.data : []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocuments(); }, []);

  const categories = useMemo(() => Array.from(new Set(documents.map((document) => document.category).filter(Boolean))), [documents]);
  const filtered = useMemo(() => documents
    .filter((document) => category === "all" || document.category === category)
    .filter((document) => `${document.filename} ${document.category} ${document.source}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === "name") return String(a.filename).localeCompare(String(b.filename));
      const aTime = new Date(a.uploaded_at || 0).getTime();
      const bTime = new Date(b.uploaded_at || 0).getTime();
      return sort === "oldest" ? aTime - bTime : bTime - aTime;
    }), [documents, category, search, sort]);

  const removeDocument = async (document: any) => {
    if (!window.confirm(`Delete "${document.filename}" from the intelligence library?`)) return;
    try {
      await api.delete(`/documents/${document.id}`);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      if (selectedDoc?.id === document.id) setSelectedDoc(null);
    } catch {
      window.alert("Unable to delete this intelligence document.");
    }
  };

  const openDetail = (document: any, tab: "preview" | "summary") => {
    setSelectedDoc(document);
    setDetailTab(tab);
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="Document command"
        title="Intelligence Library"
        description="Search, inspect, and manage all reports indexed within the secure intelligence environment."
        action={<button className="button button--primary" onClick={() => navigate("/upload")}><Icon name="upload" />Ingest document</button>}
      />

      <section className="toolbar">
        <label className="toolbar-search"><Icon name="search" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search filename, category, or source..." /></label>
        <div className="toolbar-controls">
          <label className="select-shell"><Icon name="filter" size={15} /><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select><Icon name="chevron" size={14} /></label>
          <label className="select-shell"><select value={sort} onChange={(event) => setSort(event.target.value as SortMode)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name">Filename A–Z</option></select><Icon name="chevron" size={14} /></label>
          <div className="view-toggle">
            <button className={view === "grid" ? "active" : ""} onClick={() => setView("grid")} aria-label="Grid view"><Icon name="grid" size={16} /></button>
            <button className={view === "list" ? "active" : ""} onClick={() => setView("list")} aria-label="List view"><Icon name="list" size={16} /></button>
          </div>
        </div>
      </section>

      <div className="result-meta"><span>{filtered.length} intelligence {filtered.length === 1 ? "document" : "documents"}</span><span>Secure index synchronized</span></div>

      {loading ? <LoadingState /> : error ? <ErrorState onRetry={fetchDocuments} /> : !filtered.length ? (
        <EmptyState title={documents.length ? "No matching intelligence" : "Library awaiting intelligence"} description={documents.length ? "Adjust your search or filters to broaden the results." : "Upload your first report to create the secure intelligence index."} action={!documents.length && <button className="button button--secondary" onClick={() => navigate("/upload")}><Icon name="upload" />Open upload center</button>} />
      ) : (
        <section className={`document-collection document-collection--${view}`}>
          {filtered.map((document) => (
            <article className="document-card" key={document.id}>
              <div className="document-card__top">
                <div className="file-emblem"><Icon name="document" /><span>{String(document.filename || "file").split(".").pop()?.slice(0, 4).toUpperCase()}</span></div>
                <StatusBadge status={document.status || "Indexed"} />
              </div>
              <div className="document-card__identity">
                <h3 title={document.filename}>{document.filename || "Untitled document"}</h3>
                <p>{document.source || "Source not specified"}</p>
              </div>
              <div className="document-card__facts">
                <div><span>Category</span><strong>{document.category || "Unclassified"}</strong></div>
                <div><span>Uploaded</span><strong>{safeDate(document.uploaded_at)}</strong></div>
                <div><span>Pages</span><strong>{document.pages ?? document.page_count ?? "—"}</strong></div>
                <div><span>Chunks</span><strong>{document.chunks ?? document.chunk_count ?? "—"}</strong></div>
              </div>
              <div className="document-card__actions">
                <button onClick={() => openDetail(document, "preview")}><Icon name="eye" size={15} />View</button>
                <button onClick={() => openDetail(document, "summary")}><Icon name="spark" size={15} />Analyze</button>
                <button className="danger" onClick={() => removeDocument(document)} aria-label={`Delete ${document.filename}`}><Icon name="trash" size={15} /></button>
              </div>
            </article>
          ))}
        </section>
      )}

      {selectedDoc && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedDoc(null); }}>
          <section className="document-modal" role="dialog" aria-modal="true">
            <header>
              <div className="file-emblem"><Icon name="document" /><span>{String(selectedDoc.filename).split(".").pop()?.toUpperCase()}</span></div>
              <div><span className="eyebrow">{selectedDoc.category || "Intelligence document"}</span><h2>{selectedDoc.filename}</h2><p>{selectedDoc.source || "Source not specified"} · {safeDate(selectedDoc.uploaded_at)}</p></div>
              <button className="icon-button" onClick={() => setSelectedDoc(null)} aria-label="Close preview"><Icon name="close" /></button>
            </header>
            <div className="modal-tabs">
              <button className={detailTab === "preview" ? "active" : ""} onClick={() => setDetailTab("preview")}>Document preview</button>
              <button className={detailTab === "summary" ? "active" : ""} onClick={() => setDetailTab("summary")}>AI summary</button>
            </div>
            <div className="document-modal__content">
              {detailTab === "preview" ? <Preview preview={selectedDoc.preview} /> : selectedDoc.summary ? <div className="summary-copy">{selectedDoc.summary}</div> : <EmptyState icon="spark" title="AI summary unavailable" description="This document is indexed, but the current service did not provide a summary." />}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
