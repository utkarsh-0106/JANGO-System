import { useState } from "react";
import { Link } from "react-router-dom";

import api from "../api/axios";

import chatAI from "../assets/chat-ai.png";
import jangoAvatar from "../assets/jango-avatar.png";
import logo from "../assets/logo.png";
export default function Chat() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedSource, setSelectedSource] = useState(null);
  const [sourceError, setSourceError] = useState("");
  const [openingSource, setOpeningSource] = useState(false);

  async function handleAsk(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setError("");

    const userMessage = {
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const response = await api.post("/api/rag/query", {
        question: trimmedQuestion,
        top_k: 5,
      });

      const data = response.data || {};
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer || "Jango returned an empty answer.",
          sources: Array.isArray(data.sources) ? data.sources : [],
          usage: data.usage || null,
          question: trimmedQuestion,
        },
      ]);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to get an answer. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  function renderHighlightedPassage(text, questionText = "") {
    if (!text) return "No supporting passage was returned for this source.";
    const stopWords = new Set(["what", "does", "this", "that", "with", "from", "about", "have", "which", "where", "when", "who", "the", "and", "for", "are", "was"]);
    const terms = [...new Set(questionText.toLowerCase().match(/[a-z0-9][a-z0-9_-]{2,}/g) || [])]
      .filter((term) => !stopWords.has(term)).slice(0, 12);
    if (!terms.length) return text;
    const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
    return text.split(pattern).map((part, index) =>
      terms.some((term) => part.toLowerCase() === term)
        ? <mark key={`${part}-${index}`} className="citation-highlight">{part}</mark>
        : part
    );
  }

  async function openCitedPdf(source) {
    if (!source?.id) {
      setSourceError("This citation does not include a document ID, so its PDF cannot be opened.");
      return;
    }
    setOpeningSource(true);
    setSourceError("");
    try {
      const response = await api.get(`/api/documents/${source.id}/file`, { responseType: "blob" });
      const pdfUrl = URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
      const page = Math.max(1, Number.parseInt(source.page_number, 10) || 1);
      const opened = window.open(`${pdfUrl}#page=${page}`, "_blank");
      if (!opened) {
        const link = document.createElement("a");
        link.href = `${pdfUrl}#page=${page}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 120_000);
    } catch (err) {
      setSourceError(err.response?.data?.detail || "Could not open this PDF. Confirm the document still exists and try again.");
    } finally {
      setOpeningSource(false);
    }
  }

  function useSuggestion(text) {
    setQuestion(text);
  }

  return (
    <div className="chat-page jango-chat-page">
      <nav className="navbar jango-navbar">
        <Link to="/dashboard" className="jango-brand">
          <img src={logo} alt="Jango" />
          <span>
            <strong>JANGO</strong>
            <small>PRIVATE AI</small>
          </span>
        </Link>

        <div className="jango-nav-links">
          <Link to="/dashboard">
            Dashboard
          </Link>

          <Link className="active" to="/chat">
            Ask Jango
          </Link>
        </div>

        <div className="jango-chat-nav-actions">
<Link to="/dashboard" className="back-button">
            ← Dashboard
          </Link>
        </div>
      </nav>

      <main className="chat-content jango-chat-content">
        <header className="chat-header">
          <p className="eyebrow">PRIVATE KNOWLEDGE ASSISTANT</p>
          <h1>Ask Jango</h1>
          <p>
            Ask questions about your uploaded documents and get
            answers grounded in their content.
          </p>
        </header>

        <section className="chat-container">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-ai-visual">
                <img
                  src={chatAI}
                  alt="Jango AI assistant"
                />
              </div>

              <div className="chat-empty-copy">
                <span className="chat-online">
                  <span />
                  JANGO IS READY
                </span>

                <h2>Hello, I'm Jango 👋</h2>

                <p>
                  Ask me anything about your uploaded documents.
                  I'll find the answer using your private knowledge
                  base.
                </p>
              </div>

              <div className="suggested-questions">
                <button
                  onClick={() =>
                    useSuggestion(
                      "What programming languages and technical skills does this person have?"
                    )
                  }
                >
                  <span>↗</span>
                  What are the technical skills?
                </button>

                <button
                  onClick={() =>
                    useSuggestion(
                      "What projects has this person worked on?"
                    )
                  }
                >
                  <span>↗</span>
                  What projects are mentioned?
                </button>

                <button
                  onClick={() =>
                    useSuggestion(
                      "Summarize this person's experience."
                    )
                  }
                >
                  <span>↗</span>
                  Summarize the experience
                </button>
              </div>
            </div>
          )}

          <div className="messages">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message-row ${message.role}`}
              >
                <div className="message-avatar">
                  {message.role === "user" ? (
                    "U"
                  ) : (
                    <img
                      src={jangoAvatar}
                      alt=""
                    />
                  )}
                </div>

                <div className="message-body">
                  <span className="message-role">
                    {message.role === "user"
                      ? "You"
                      : "Jango"}
                  </span>

                  <div className="message-content">
                    {message.content}
                  </div>

                  {message.role === "assistant" && message.usage && (
                    <div className="message-usage">
                      <span>{Number(message.usage.total_tokens || 0).toLocaleString()} tokens</span>
                      <span>{message.usage.latency_ms ? `${Math.round(message.usage.latency_ms)} ms` : "—"}</span>
                      <span>{message.usage.provider}/{message.usage.model}</span>
                      <span>${Number(message.usage.estimated_cost_usd || 0).toFixed(4)}</span>
                    </div>
                  )}

                  {message.role === "assistant" &&
                    message.sources?.length > 0 && (
                      <div className="sources">
                        <h3>Sources</h3>

                        {message.sources.map(
                          (source, sourceIndex) => (
                            <button
                              type="button"
                              className="source-card source-card-button"
                              key={`${source.id || source.filename}-${sourceIndex}`}
                              onClick={() => { setSelectedSource({ ...source, question: message.question || "" }); setSourceError(""); }}
                              aria-label={`View source ${source.filename || "document"}, page ${source.page_number || "unknown"}`}
                            >
                              <div className="source-number">{sourceIndex + 1}</div>
                              <div className="source-card-copy">
                                <strong>{source.filename || "Document"}</strong>
                                <span>Page {source.page_number || "—"}</span>
                              </div>
                              <span className="source-open-label">View evidence ↗</span>
                            </button>
                          )
                        )}
                      </div>
                    )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row assistant">
                <div className="message-avatar">
                  <img
                    src={jangoAvatar}
                    alt=""
                  />
                </div>

                <div className="message-body">
                  <span className="message-role">
                    Jango
                  </span>

                  <div className="typing-indicator">
                    <span />
                    <span />
                    <span />
                    <em>
                      Searching your knowledge base...
                    </em>
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="alert alert-error chat-error">
              <span>⚠</span>
              {error}
            </div>
          )}

          <form
            className="chat-input-area"
            onSubmit={handleAsk}
          >
            <textarea
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="Ask something about your documents..."
              rows="1"
              disabled={loading}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();
                  event.currentTarget.form.requestSubmit();
                }
              }}
            />

            <button
              type="submit"
              disabled={
                loading || !question.trim()
              }
            >
              {loading ? "Thinking..." : "Ask Jango ↑"}
            </button>
          </form>

          <p className="chat-disclaimer">
            Jango answers using your private document knowledge
            base. Sources are shown with each answer.
          </p>
        </section>
      </main>

      {selectedSource && (
        <div className="citation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedSource(null); }}>
          <section className="citation-modal" role="dialog" aria-modal="true" aria-labelledby="citation-title">
            <button type="button" className="citation-modal-close" onClick={() => setSelectedSource(null)} aria-label="Close citation">×</button>
            <span className="citation-eyebrow">SOURCE EVIDENCE</span>
            <h2 id="citation-title">{selectedSource.filename || "Document source"}</h2>
            <p className="citation-page-label">Page {selectedSource.page_number || "—"}</p>
            <p className="citation-help">Supporting passage from the retrieved document. Matching terms from your question are highlighted below.</p>
            <blockquote className="citation-passage">{renderHighlightedPassage(selectedSource.content, selectedSource.question)}</blockquote>
            {sourceError && <p className="citation-error">{sourceError}</p>}
            <div className="citation-modal-actions">
              <button type="button" className="citation-open-pdf" disabled={openingSource} onClick={() => openCitedPdf(selectedSource)}>{openingSource ? "Opening PDF…" : `Open original PDF · page ${selectedSource.page_number || 1} ↗`}</button>
              <button type="button" className="citation-cancel" onClick={() => setSelectedSource(null)}>Close</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
