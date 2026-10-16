import { useEffect, useRef, useState } from "react";
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
  const [responseLanguage, setResponseLanguage] = useState("auto");
  const [listening, setListening] = useState(false);
  const [speakingMessage, setSpeakingMessage] = useState(null);
  const [voiceError, setVoiceError] = useState("");
  const recognitionRef = useRef(null);
  const utteranceRef = useRef(null);

  useEffect(() => () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* already stopped */ }
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  useEffect(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeakingMessage(null);
  }, [responseLanguage]);

  async function handleAsk(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setError("");
    stopSpeaking();

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
        response_language: responseLanguage,
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


  function toggleVoiceInput() {
    setVoiceError("");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported in this browser. Try the latest Chrome or Edge, or type your question.");
      return;
    }
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = responseLanguage === "english" ? "en-IN" : "hi-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((result) => result[0]?.transcript || "").join(" ");
      setQuestion(transcript);
    };
    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": "Microphone permission was denied. Allow microphone access for localhost in your browser settings.",
        network: "Speech recognition could not reach the browser's speech service. Check your internet connection and try again, or type your question.",
        "no-speech": "No speech was detected. Move closer to the microphone and try again.",
        "audio-capture": "No microphone was found. Check your Mac's microphone settings and try again.",
      };
      setVoiceError(messages[event.error] || `Voice input failed (${event.error}). You can still type your question.`);
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      setVoiceError("Could not start the microphone. Please try again or type your question.");
      setListening(false);
    }
  }

  function stopSpeaking() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    utteranceRef.current = null;
    setSpeakingMessage(null);
  }

  function speakAnswer(text, messageIndex) {
    if (!text) return;
    if (!("speechSynthesis" in window)) {
      setVoiceError("Voice output is not supported in this browser. Try the latest Chrome or Edge.");
      return;
    }
    if (speakingMessage === messageIndex && window.speechSynthesis.speaking) {
      stopSpeaking();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const language = responseLanguage === "english" ? "en-IN" : responseLanguage === "hindi" ? "hi-IN" : "hi-IN";
    utterance.lang = language;
    utterance.rate = 0.92;
    utterance.onend = () => {
      if (utteranceRef.current === utterance) {
        utteranceRef.current = null;
        setSpeakingMessage(null);
      }
    };
    utterance.onerror = () => {
      if (utteranceRef.current === utterance) {
        utteranceRef.current = null;
        setSpeakingMessage(null);
      }
    };
    utteranceRef.current = utterance;
    setSpeakingMessage(messageIndex);
    window.speechSynthesis.speak(utterance);
  }

  function renderAnswer(text) {
    const lines = String(text || "").replace(/\r/g, "").split("\n");
    const blocks = [];
    let listItems = [];
    const inlineFormat = (value) => value.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
      return part;
    });
    const flushList = () => {
      if (listItems.length) {
        blocks.push(<ul key={`list-${blocks.length}`}>{listItems.map((item, i) => <li key={i}>{inlineFormat(item)}</li>)}</ul>);
        listItems = [];
      }
    };
    lines.forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) { flushList(); return; }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/);
      if (bullet) { listItems.push(bullet[1]); return; }
      flushList();
      if (heading) {
        const Tag = heading[1].length === 1 ? "h3" : "h4";
        blocks.push(<Tag key={`heading-${blocks.length}`}>{inlineFormat(heading[2])}</Tag>);
      } else {
        blocks.push(<p key={`paragraph-${blocks.length}`}>{inlineFormat(line)}</p>);
      }
    });
    flushList();
    return blocks;
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

  function handleSuggestion(text) {
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
            Ask questions in English, Hindi, or Hinglish. Answers remain grounded in your uploaded documents.
          </p>
          <div className="jango-language-control">
            <label htmlFor="jango-response-language">Reply language</label>
            <select id="jango-response-language" value={responseLanguage} onChange={(event) => setResponseLanguage(event.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="english">English</option>
              <option value="hindi">Hindi (हिन्दी)</option>
              <option value="hinglish">Hinglish</option>
            </select>
          </div>
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
                    handleSuggestion(
                      "What programming languages and technical skills does this person have?"
                    )
                  }
                >
                  <span>↗</span>
                  What are the technical skills?
                </button>

                <button
                  onClick={() =>
                    handleSuggestion(
                      "What projects has this person worked on?"
                    )
                  }
                >
                  <span>↗</span>
                  What projects are mentioned?
                </button>

                <button
                  onClick={() =>
                    handleSuggestion(
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

                  <div className={`message-content${message.role === "assistant" ? " jango-formatted-answer" : ""}`}>
                    {message.role === "assistant" ? renderAnswer(message.content) : message.content}
                  </div>

                  {message.role === "assistant" && (
                    <button type="button" className={`jango-speak-button${speakingMessage === index ? " is-speaking" : ""}`} onClick={() => speakAnswer(message.content, index)} aria-label={speakingMessage === index ? "Stop speaking" : "Read answer aloud"}>
                      {speakingMessage === index ? "⏹ Stop speaking" : "🔊 Listen"}
                    </button>
                  )}

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
            <button type="button" className={`jango-mic-button${listening ? " is-listening" : ""}`} onClick={toggleVoiceInput} disabled={loading} aria-label={listening ? "Stop voice input" : "Start voice input"} title={listening ? "Stop listening" : "Ask using your voice"}>
              {listening ? "■ Stop" : "🎙 Speak"}
            </button>
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

          {voiceError && <p className="jango-voice-error" role="status">{voiceError}</p>}

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
