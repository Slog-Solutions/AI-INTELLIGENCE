import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export default function ChatPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userQuery = query;
    setQuery("");
    setMessages(prev => [...prev, { role: "user", content: userQuery }]);
    setLoading(true);

    try {
      const res = await api.post("/chat/query", { query: userQuery });
      setMessages(prev => [...prev, { 
        role: "assistant", 
        content: res.data.answer, 
        sources: res.data.sources 
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, { 
        role: "assistant", 
        content: `Error: ${err.response?.data?.detail || "Failed to connect to intelligence engine."}` 
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-white">
      <header className="p-4 border-b border-slate-800 bg-slate-900 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate("/dashboard")} className="text-slate-400 hover:text-white">← Back</button>
          <h1 className="text-xl font-bold">ATIP AI Assistant</h1>
        </div>
        <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Secure Intelligence Link</div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 max-w-md mx-auto text-center">
            <div className="text-5xl mb-4">🎖️</div>
            <h2 className="text-xl font-bold text-slate-300 mb-2">Awaiting Instructions</h2>
            <p>Ask about training performance, unit readiness, or specific reports. I will retrieve relevant data from the secure vector store.</p>
            <div className="grid grid-cols-1 gap-2 mt-6 w-full">
              {["Summarize recent training performance.", "Which unit is most ready?", "Show trends in fuel consumption."].map(q => (
                <button key={q} onClick={() => setQuery(q)} className="text-sm bg-slate-900 hover:bg-slate-800 p-3 rounded-xl border border-slate-800 text-cyan-400 text-left transition-colors">
                  "{q}"
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl p-4 ${m.role === "user" ? "bg-cyan-700 text-white" : "bg-slate-900 border border-slate-800"}`}>
              <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-800">
                  <div className="text-xs font-bold text-slate-500 uppercase mb-2">Sources Cited:</div>
                  <div className="flex flex-wrap gap-2">
                    {m.sources.map(s => (
                      <span key={s} className="text-[10px] bg-slate-800 px-2 py-1 rounded border border-slate-700 text-cyan-400">{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce [animation-delay:0.4s]"></div>
              </div>
              <span className="text-sm text-slate-400">Analyzing Intelligence...</span>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      <footer className="p-4 bg-slate-900 border-t border-slate-800">
        <form onSubmit={handleQuery} className="max-w-4xl mx-auto flex gap-4">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about the documents..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-cyan-500 transition-colors"
          />
          <button disabled={loading || !query.trim()} className="bg-cyan-600 hover:bg-cyan-500 px-6 py-3 rounded-xl font-bold transition-colors disabled:opacity-50">
            Send
          </button>
        </form>
      </footer>
    </div>
  );
}
