import { useState } from "react";
import api from "../services/api";

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<string[]>([]);

  const handleQuery = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const response = await api.post("/chat/query", { query });
      setAnswer(response.data.answer);
      setSources(response.data.sources);
    } catch (err) {
      setAnswer("Failed to get response.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <div className="max-w-4xl mx-auto rounded-3xl bg-slate-900 p-8 shadow-xl">
        <h1 className="text-3xl font-bold mb-4">AI Assistant</h1>
        <form onSubmit={handleQuery} className="space-y-4">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={5}
            className="w-full rounded-2xl bg-slate-950 border border-slate-700 p-4 text-white"
            placeholder="Ask a question about uploaded documents..."
          />
          <button className="rounded-full bg-cyan-600 px-6 py-3 font-semibold">Ask</button>
        </form>
        {answer && (
          <div className="mt-6 rounded-2xl bg-slate-800 p-6">
            <h2 className="text-xl font-semibold">Answer</h2>
            <p className="mt-3 text-slate-200 whitespace-pre-wrap">{answer}</p>
            <div className="mt-4 text-slate-400">
              <strong>Sources:</strong> {sources.join(", ")}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
