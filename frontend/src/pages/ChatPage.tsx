import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api, { chatApi } from "../services/api";
import Icon from "../components/Icons";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: { filename: string; page_number?: number }[];
  error?: boolean;
}

const suggestions = [
  "Summarize recent training performance",
  "Identify readiness risks across units",
  "Compare trends in uploaded reports",
];

function renderMessage(content: string) {
  return content.split("\n").map((line, index) => {
    if (line.startsWith("### ")) return <h4 key={index}>{line.slice(4)}</h4>;
    if (line.startsWith("## ")) return <h3 key={index}>{line.slice(3)}</h3>;
    if (line.startsWith("# ")) return <h2 key={index}>{line.slice(2)}</h2>;
    if (/^[-*]\s/.test(line)) return <li key={index}>{line.slice(2)}</li>;
    const parts = line.split(/(\*\*.*?\*\*)/g);
    return <p key={index}>{parts.map((part, i) => part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part)}</p>;
  });
}

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const conversationIdParam = searchParams.get("c");

  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(
    conversationIdParam ? parseInt(conversationIdParam) : null
  );

  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (conversationIdParam) {
      const id = parseInt(conversationIdParam);
      setConversationId(id);
      loadConversation(id);
    } else {
      setConversationId(null);
      setMessages([]);
    }
  }, [conversationIdParam]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const loadConversation = async (id: number) => {
    try {
      const response = await chatApi.getConversation(id);
      setMessages(response.data.messages);
    } catch (error) {
      console.error("Failed to load conversation", error);
    }
  };

  const submitQuery = async () => {
    if ((!query.trim() && !attachment) || loading) return;
    const userQuery = query.trim();
    setQuery("");
    setMessages((current) => [...current, { role: "user", content: userQuery || "Analyze attached file" }]);
    setLoading(true);

    try {
      let response;
      if (attachment) {
        response = await chatApi.queryWithFile(userQuery || "Analyze this file", attachment);
        setAttachment(null);
      } else {
        response = await chatApi.queryChat(userQuery, conversationId || undefined);
      }

      if (response.data.conversation_id && !conversationId) {
        setConversationId(response.data.conversation_id);
        setSearchParams({ c: response.data.conversation_id.toString() });
      }

      setMessages((current) => [...current, {
        role: "assistant",
        content: response.data?.answer || "The intelligence engine returned no written assessment.",
        sources: response.data?.sources || [],
      }]);
    } catch {
      setMessages((current) => [...current, {
        role: "assistant",
        content: "Intelligence service temporarily unavailable. Your request was not processed; please retry when the secure engine is online.",
        error: true,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const copyResponse = async (content: string, index: number) => {
    await navigator.clipboard.writeText(content);
    setCopied(index);
    window.setTimeout(() => setCopied(null), 1600);
  };

  const acceptFile = (file?: File) => {
    if (file) setAttachment(file);
    setDragging(false);
  };

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div>
          <span className="eyebrow">Secure AI channel</span>
          <h1>Intelligence Assistant</h1>
        </div>
        <div className="model-badge"><i />ATIP local inference</div>
      </header>

      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__emblem"><Icon name="spark" size={32} /></div>
            <span className="eyebrow">Ready for tasking</span>
            <h2>Upload intelligence reports<br />or ask a question.</h2>
            <p>Analyze operational documents, surface training patterns, and retrieve grounded answers from the secure intelligence library.</p>
            <div className="prompt-suggestions">
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => { setQuery(suggestion); inputRef.current?.focus(); }}>
                  <span>{suggestion}</span><Icon name="arrow" size={16} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-stream">
            {messages.map((message, index) => (
              <article key={index} className={`message message--${message.role} ${message.error ? "message--error" : ""}`}>
                <div className="message__avatar">
                  {message.role === "assistant" ? <Icon name="shield" size={18} /> : <Icon name="user" size={18} />}
                </div>
                <div className="message__body">
                  <div className="message__meta">
                    <strong>{message.role === "assistant" ? "ATIP Intelligence" : "You"}</strong>
                    <span>{message.role === "assistant" ? "Grounded response" : "Operator query"}</span>
                  </div>
                  <div className="message__content">{renderMessage(message.content)}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="source-citations">
                      <span><Icon name="library" size={14} />Source citations</span>
                      <div>{message.sources.map((source, sourceIndex) => (
                        <button key={sourceIndex}>
                          [{sourceIndex + 1}] {source.filename} {source.page_number ? `(p. ${source.page_number})` : ""}
                        </button>
                      ))}</div>
                    </div>
                  )}
                  {message.role === "assistant" && (
                    <button className="copy-button" onClick={() => copyResponse(message.content, index)}>
                      <Icon name={copied === index ? "check" : "copy"} size={15} />{copied === index ? "Copied" : "Copy response"}
                    </button>
                  )}
                </div>
              </article>
            ))}
            {loading && (
              <article className="message message--assistant">
                <div className="message__avatar"><Icon name="shield" size={18} /></div>
                <div className="message__body">
                  <div className="message__meta"><strong>ATIP Intelligence</strong><span>Analyzing sources</span></div>
                  <div className="thinking"><span /><span /><span /><p>Thinking through available intelligence</p></div>
                </div>
              </article>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div
        className={`composer-wrap ${dragging ? "composer-wrap--dragging" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); acceptFile(event.dataTransfer.files[0]); }}
      >
        {dragging && <div className="drop-overlay"><Icon name="upload" />Drop report to attach</div>}
        <div className="composer">
          {attachment && <div className="attachment-chip"><Icon name="document" size={15} /><span>{attachment.name}</span><button onClick={() => setAttachment(null)}><Icon name="close" size={13} /></button></div>}
          <textarea
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submitQuery();
              }
            }}
            placeholder={attachment ? "Ask a question about this file..." : "Ask ATIP about your intelligence documents..."}
            rows={1}
          />
          <div className="composer__actions">
            <input ref={fileRef} type="file" hidden onChange={(event) => acceptFile(event.target.files?.[0])} />
            <button className="icon-button" onClick={() => fileRef.current?.click()} aria-label="Attach document"><Icon name="attach" /></button>
            <span>Enter to send · Shift + Enter for new line</span>
            <button className="send-button" disabled={(!query.trim() && !attachment) || loading} onClick={submitQuery} aria-label="Send message"><Icon name="send" size={17} /></button>
          </div>
        </div>
        <p className="composer-note">ATIP can make mistakes. Validate critical intelligence against primary sources.</p>
      </div>
    </div>
  );
}
