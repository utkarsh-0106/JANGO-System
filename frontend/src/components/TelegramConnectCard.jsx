import { useEffect, useState } from "react";
import api from "../api/axios";

export default function TelegramConnectCard() {
  const [status, setStatus] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refreshStatus() {
    try {
      const response = await api.get("/api/telegram/status");
      setStatus(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to check Telegram connection.");
    }
  }

  useEffect(() => { refreshStatus(); }, []);

  async function createCode() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await api.post("/api/telegram/link-code");
      setCode(response.data.code);
      setNotice("Code expires in 10 minutes. Send /link followed by this code to your JANGO bot in a private chat.");
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to generate a Telegram link code.");
    } finally {
      setBusy(false);
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(`/link ${code}`);
      setNotice("Link command copied. Paste it into your private JANGO Telegram chat.");
    } catch {
      setNotice(`In Telegram, send: /link ${code}`);
    }
  }

  return (
    <section className="telegram-connect-card" aria-label="Telegram document delivery">
      <div className="telegram-connect-heading">
        <div>
          <p className="eyebrow">DOCUMENT DELIVERY</p>
          <h2>Send work to Telegram</h2>
          <p>Deliver original PDFs, AI summaries, and generated reports to your private JANGO Telegram chat.</p>
        </div>
        <span className={`telegram-status-pill ${status?.linked ? "is-connected" : ""}`}>
          {status?.linked ? "Connected" : status ? "Not connected" : "Checking…"}
        </span>
      </div>
      {status && !status.configured && <p className="telegram-feedback error">Telegram is not configured on the backend.</p>}
      {error && <p className="telegram-feedback error" role="alert">{error}</p>}
      {notice && <p className="telegram-feedback" role="status">{notice}</p>}
      {code && (
        <div className="telegram-code-panel">
          <code>{code}</code>
          <button type="button" onClick={copyCode}>Copy /link command</button>
        </div>
      )}
      <div className="telegram-connect-actions">
        {!status?.linked && (
          <button type="button" className="telegram-action-button" onClick={createCode} disabled={busy || !status?.configured}>
            {busy ? "Generating…" : "Connect Telegram"}
          </button>
        )}
        <a className="telegram-action-button secondary" href="https://t.me/JANGO_Document_AI_bot" target="_blank" rel="noreferrer">
          Open Telegram bot ↗
        </a>
        {status?.linked && <button type="button" className="telegram-action-button secondary" onClick={refreshStatus}>Refresh status</button>}
      </div>
    </section>
  );
}
