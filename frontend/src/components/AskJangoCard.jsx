import { useState } from "react";

import api from "../api/axios";
import jangoAvatar from "../assets/jango-avatar.png";

export default function AskJangoCard({ documentCount = 0 }) {

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAsk(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    setError("");
    setAnswer("");
    setSources([]);
    setLoading(true);

    try {

      const response = await api.post("/api/rag/query", {
        question: trimmedQuestion,
        top_k: 5,
      });

      setAnswer(response.data.answer || "No answer was returned.");
      setSources(response.data.sources || []);

      setQuestion("");

    } catch (err) {

      setError(
        err.response?.data?.detail ||
        "Unable to get an answer. Please try again."
      );

    } finally {

      setLoading(false);

    }
  }

  return (

    <aside className="ask-jango-rail">

      <div className="ask-jango-card">

        {/* Header */}

        <div className="ask-jango-card-header">

          <div className="ask-jango-icon">
            ✦
          </div>

          <div>
            <span className="ask-jango-kicker">
              AI ASSISTANT
            </span>

            <h3>
              Ask Jango
            </h3>
          </div>

        </div>


        {/* Jango Image */}

        <div className="ask-jango-visual">

          <img
            src={jangoAvatar}
            alt="Jango AI assistant"
          />

        </div>


        {/* Status */}

        <div className="ask-jango-content">

          <div className="ai-status">

            <span className="ai-status-dot" />

            Jango is online

          </div>

          <h2>
            Your private
            <br />
            knowledge assistant.
          </h2>

          <p>
            Ask questions about your uploaded
            documents and get answers grounded
            in your private knowledge base.
          </p>

        </div>


        {/* Answer */}

        {answer && (

          <div className="ask-jango-answer">

            <div className="ask-jango-answer-header">

              <img
                src={jangoAvatar}
                alt=""
              />

              <span>
                Jango
              </span>

            </div>

            <p>
              {answer}
            </p>

            {sources.length > 0 && (

              <div className="ask-jango-sources">

                <span>
                  Sources
                </span>

                {sources.slice(0, 3).map(
                  (source, index) => (

                    <small key={index}>

                      {source.filename || "Document"}

                      {source.page_number
                        ? ` · Page ${source.page_number}`
                        : ""}

                    </small>

                  )
                )}

              </div>

            )}

          </div>

        )}


        {/* Error */}

        {error && (

          <div className="ask-jango-error">

            {error}

          </div>

        )}


        {/* Ask Input */}

        <form
          className="ask-jango-form"
          onSubmit={handleAsk}
        >

          <textarea
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            placeholder="Ask about your documents..."
            rows="2"
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
              loading ||
              !question.trim()
            }
          >

            {loading
              ? "Thinking..."
              : "Ask Jango ↑"}

          </button>

        </form>


        {/* Stats */}

        <div className="ask-jango-stats">

          <div>

            <strong>
              {documentCount}
            </strong>

            <span>
              Documents
            </span>

          </div>

          <div>

            <strong>
              RAG
            </strong>

            <span>
              Enabled
            </span>

          </div>

        </div>


        <p className="ask-jango-footer">

          Answers are generated from your private
          document knowledge base.

        </p>

      </div>

    </aside>

  );
}
