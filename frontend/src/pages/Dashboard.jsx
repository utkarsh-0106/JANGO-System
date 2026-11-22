import logo from "../assets/logo.webp";
import jangoAvatar from "../assets/jango-avatar.webp";


import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import api from "../api/axios";

import aiHero from "../assets/ai-hero.webp";
import documentsImage from "../assets/documents.webp";

import Sidebar from "../components/Sidebar";
import AskJangoCard from "../components/AskJangoCard";
import TelegramConnectCard from "../components/TelegramConnectCard";


function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDate(date) {
  if (!date) return "—";
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function statusLabel(status) {
  return status
    ? status.charAt(0).toUpperCase() + status.slice(1)
    : "Unknown";
}

export default function Dashboard() {
  const { user, logout } = useAuth();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const [sendingTelegramId, setSendingTelegramId] = useState(null);

  const fileInputRef = useRef(null);
  const uploadLockRef = useRef(false);

  async function fetchDocuments() {
    try {
      setError("");
      const response = await api.get("/api/documents/");
      setDocuments(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail || "Unable to load your documents."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDocuments();
    // Keep background ingestion state visible without requiring manual refresh.
    const pollId = window.setInterval(async () => {
      try {
        const response = await api.get("/api/documents/");
        setDocuments(response.data);
      } catch {
        // Keep the last known document state; explicit refresh surfaces errors.
      }
    }, 7000);
    return () => window.clearInterval(pollId);
  }, []);

  async function handleUpload(event) {
    const selectedFiles = Array.from(event.target.files || []);
    if (selectedFiles.length === 0 || uploadLockRef.current) return;

    uploadLockRef.current = true;
    setError("");
    setSuccess("");
    setUploading(true);

    const uploaded = [];
    const failed = [];
    const maxFileSize = 10 * 1024 * 1024;

    try {
      // Keep the existing single-file API contract and upload files one by one.
      // This avoids oversized multipart requests and lets each PDF ingest independently.
      for (const file of selectedFiles) {
        const allowedExtensions = [".pdf", ".docx", ".pptx", ".odt", ".txt", ".md", ".log", ".rtf", ".csv", ".xlsx", ".xls", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"];
        const extension = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
        if (!allowedExtensions.includes(extension)) {
          failed.push(`${file.name}: unsupported file type`);
          continue;
        }

        if (file.size > maxFileSize) {
          failed.push(`${file.name}: exceeds the 10 MB limit`);
          continue;
        }

        if (file.size === 0) {
          failed.push(`${file.name}: file is empty`);
          continue;
        }

        try {
          const formData = new FormData();
          formData.append("file", file);
          // One stable key per file operation: retries of this operation must reuse it.
          const idempotencyKey = crypto.randomUUID();
          await api.post("/api/documents/upload", formData, {
            headers: {
              "Content-Type": "multipart/form-data",
              "Idempotency-Key": idempotencyKey,
            },
          });
          uploaded.push(file.name);
        } catch (err) {
          const detail = err.response?.data?.detail || "upload failed";
          failed.push(`${file.name}: ${detail}`);
        }
      }

      if (uploaded.length > 0) {
        setSuccess(
          `${uploaded.length} file${uploaded.length === 1 ? "" : "s"} uploaded successfully: ${uploaded.join(", ")}. Processing continues in the background.`
        );
      }

      if (failed.length > 0) {
        setError(`Could not upload ${failed.length} file${failed.length === 1 ? "" : "s"}: ${failed.join("; ")}`);
      }

      await fetchDocuments();
    } finally {
      uploadLockRef.current = false;
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleSendToTelegram(document) {
    setSendingTelegramId(document.id);
    setError("");
    setSuccess("");
    try {
      await api.post("/api/telegram/send", { kind: "document", document_id: document.id });
      setSuccess(`${document.filename} was sent to your Telegram chat.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to send this document to Telegram.");
    } finally {
      setSendingTelegramId(null);
    }
  }

  async function handleRetry(document) {
    setError("");
    setSuccess("");
    try {
      await api.post(`/api/documents/${document.id}/retry`);
      setSuccess(`Reprocessing started for ${document.filename}.`);
      await fetchDocuments();
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to retry document processing.");
    }
  }

  async function handleDelete(documentId, filename) {
    const confirmed = window.confirm(
      `Delete "${filename}"?\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingId(documentId);
    setError("");
    setSuccess("");

    try {
      await api.delete(`/api/documents/${documentId}`);

      setDocuments((current) =>
        current.filter((document) => document.id !== documentId)
      );

      setSuccess(`${filename} was deleted.`);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to delete the document."
      );
    } finally {
      setDeletingId(null);
    }
  }

  const totalDocuments = documents.length;

  const readyDocuments = documents.filter(
    (document) => document.status === "ready"
  ).length;

  const processingDocuments = documents.filter(
    (document) =>
      document.status === "processing" ||
      document.status === "uploaded"
  ).length;

  const failedDocuments = documents.filter(
    (document) => document.status === "failed"
  ).length;

  return (
    <div className="dashboard jango-dashboard dashboard-shell">

       {/* LEFT SIDEBAR */}
    <Sidebar />

    {/* CENTER DASHBOARD */}
    <div className="dashboard-main-area">


      <main className="dashboard-content jango-dashboard-content">
        <section className="dashboard-header jango-hero">
          <div className="jango-hero-content">
            <p className="eyebrow">KNOWLEDGE BASE</p>

            <h1>
              Welcome, {user?.username} 👋
            </h1>

            <p>
              Upload your enterprise documents and build
              your private knowledge base.
            </p>

            <div className="hero-actions">
              <Link className="hero-primary" to="/chat">
                Ask Jango →
              </Link>

              <span className="hero-status">
                <span />
                Knowledge base online
              </span>
            </div>
          </div>

          <div className="jango-hero-visual">
            <img
              src={aiHero}
              alt="Jango AI knowledge network"
            />
          </div>
        </section>

        {error && (
          <div className="alert alert-error">
            <span>⚠</span>
            {error}
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <span>✓</span>
            {success}
          </div>
        )}

        <TelegramConnectCard />

        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon stat-gold">▣</div>
            <div>
              <span>Total Documents</span>
              <strong>{totalDocuments}</strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-green">✓</div>
            <div>
              <span>Ready</span>
              <strong>{readyDocuments}</strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-blue">◌</div>
            <div>
              <span>Processing</span>
              <strong>{processingDocuments}</strong>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-red">!</div>
            <div>
              <span>Failed</span>
              <strong>{failedDocuments}</strong>
            </div>
          </div>
        </section>

        <section className="upload-card">
          <div className="upload-illustration">
            <img src={documentsImage} alt="" />
          </div>

          <div className="upload-content">
            <p className="upload-kicker">DOCUMENT INGESTION</p>
            <h2>Upload documents</h2>
            <p>
              Add documents and data files to your private enterprise knowledge base.
            </p>
            <small>PDF, DOCX, PPTX, ODT, TXT, MD, LOG, RTF, CSV, XLSX, XLS, JSON, YAML, XML, HTML · Maximum 10 MB per file</small>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.pptx,.odt,.txt,.md,.log,.rtf,.csv,.xlsx,.xls,.json,.yaml,.yml,.xml,.html,.htm,application/pdf,text/plain,text/csv,application/json"
            multiple
            onChange={handleUpload}
            hidden
          />

          <button
            className="upload-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading files..." : "Choose files"}
          </button>
        </section>

        <section id="documents" className="documents-section">
          <div className="section-header">
            <div>
              <p className="eyebrow">YOUR KNOWLEDGE</p>
              <h2>Your Documents</h2>
              <p>Manage the documents in your knowledge base.</p>
            </div>

            <button
              className="refresh-button"
              onClick={fetchDocuments}
              disabled={loading}
            >
              ↻ Refresh
            </button>
          </div>

          {loading ? (
            <div className="empty-state">
              <div className="spinner" />
              <p>Loading documents...</p>
            </div>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <div className="empty-visual">
                <img src={documentsImage} alt="" />
              </div>
              <h3>No documents yet</h3>
              <p>
                Upload your first PDF to start building your
                knowledge base.
              </p>
            </div>
          ) : (
            <div className="documents-table-wrapper">
              <table className="documents-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Size</th>
                    <th>Uploaded</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>

                <tbody>
                  {documents.map((document) => (
                    <tr key={document.id}>
                      <td>
                        <div className="document-name">
                          <span className="pdf-icon">{document.filename?.split(".").pop()?.slice(0, 4).toUpperCase() || "FILE"}</span>

                          <div>
                            <strong>{document.filename}</strong>
                            <small>
                              Document #{document.id}
                              {document.status === "failed" && document.processing_error
                                ? ` · ${document.processing_error}`
                                : ""}
                            </small>
                          </div>
                        </div>
                      </td>

                      <td>{formatBytes(document.file_size)}</td>

                      <td>
                        {formatDate(document.created_at)}
                      </td>

                      <td>
                        <span
                          className={`status-badge status-${document.status}`}
                        >
                          <span className="status-dot" />
                          {statusLabel(document.status)}
                        </span>
                      </td>

                      <td className="actions-cell">
                        {document.status === "failed" && (
                          <button
                            className="refresh-button"
                            onClick={() => handleRetry(document)}
                            title="Retry document processing"
                          >
                            Retry
                          </button>
                        )}
                        <button
                          className="delete-button"
                          onClick={() =>
                            handleDelete(
                              document.id,
                              document.filename
                            )
                          }
                          disabled={
                            deletingId === document.id
                          }
                          title="Delete document"
                        >
                          {deletingId === document.id
                            ? "..."
                            : "Delete"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="chat-feature-card">
          <div className="chat-feature-content">
            <span className="next-label">
              PRIVATE KNOWLEDGE ASSISTANT
            </span>

            <h2>Ask Jango about your documents</h2>

            <p>
              Your documents are ready. Ask questions and get
              answers grounded in your uploaded documents with
              page-level sources.
            </p>

            <Link className="chat-button" to="/chat">
              Ask Jango →
            </Link>
          </div>

          <div className="chat-feature-image">
            <img
              src={jangoAvatar}
              alt="Jango AI assistant"
            />
          </div>
        </section>
      </main>
    </div>
     {/* RIGHT ASK JANGO PANEL */}
    <AskJangoCard
      documentCount={documents.length}
    />

  </div>
  );
}
