import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import api from "../api/axios";
import "./Settings.css";

const languageOptions = [
  ["auto", "Automatic"],
  ["english", "English"],
  ["hindi", "Hindi"],
  ["hinglish", "Hinglish"],
];

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm: "" });

  useEffect(() => {
    api.get("/api/settings")
      .then(({ data }) => setSettings(data))
      .catch((err) => setError(err.response?.data?.detail || "Unable to load your settings."))
      .finally(() => setLoading(false));
  }, []);

  function updateField(field, value) {
    setSettings((current) => ({ ...current, [field]: value }));
    setNotice("");
  }

  async function savePreferences(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api.put("/api/settings", {
        preferred_response_language: settings.preferred_response_language,
        retrieval_top_k: Number(settings.retrieval_top_k),
      });
      setNotice("Your preferences have been saved.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save your preferences.");
    } finally {
      setSaving(false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (passwords.new_password !== passwords.confirm) {
      setError("The new passwords do not match.");
      return;
    }
    setChangingPassword(true);
    try {
      const { confirm, ...payload } = passwords;
      await api.put("/api/settings/password", payload);
      setPasswords({ current_password: "", new_password: "", confirm: "" });
      setNotice("Your password has been changed successfully.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update your password.");
    } finally {
      setChangingPassword(false);
    }
  }

  return (
    <div className="dashboard dashboard-shell settings-shell">
      <Sidebar />
      <div className="dashboard-main-area">
        <main className="dashboard-content settings-content">
          <header className="settings-heading">
            <p className="eyebrow">WORKSPACE PREFERENCES</p>
            <h1>Settings</h1>
            <p>Manage your JANGO experience, retrieval preferences, and account security.</p>
          </header>

          {error && <div className="alert alert-error" role="alert">{error}</div>}
          {notice && <div className="alert alert-success" role="status">{notice}</div>}
          {loading ? <div className="settings-loading">Loading your settings…</div> : settings && (
            <>
              <section className="settings-card">
                <div className="settings-card-heading">
                  <span className="settings-icon">◉</span>
                  <div><h2>Account profile</h2><p>Your signed-in JANGO account details.</p></div>
                </div>
                <div className="settings-grid">
                  <label className="settings-field">
                    <span>Username</span>
                    <input value={settings.username || ""} readOnly />
                  </label>
                  <label className="settings-field">
                    <span>Email address</span>
                    <input value={settings.email || ""} readOnly />
                  </label>
                </div>
                <p className="settings-hint">Profile details are read-only in this version.</p>
              </section>

              <form className="settings-card" onSubmit={savePreferences}>
                <div className="settings-card-heading">
                  <span className="settings-icon">✧</span>
                  <div><h2>AI & retrieval preferences</h2><p>Choose how JANGO retrieves context and responds to your questions.</p></div>
                </div>
                <div className="settings-grid">
                  <label className="settings-field">
                    <span>Default response language</span>
                    <select value={settings.preferred_response_language} onChange={(e) => updateField("preferred_response_language", e.target.value)}>
                      {languageOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <small>Used as the default language in Ask Jango.</small>
                  </label>
                  <label className="settings-field">
                    <span>Retrieval results (Top-K)</span>
                    <select value={settings.retrieval_top_k} onChange={(e) => updateField("retrieval_top_k", Number(e.target.value))}>
                      {[3, 5, 8, 10, 15, 20].map((value) => <option key={value} value={value}>{value} results</option>)}
                    </select>
                    <small>Number of relevant document chunks passed to the answer generation step.</small>
                  </label>
                </div>
                <div className="settings-actions"><button className="settings-primary" type="submit" disabled={saving}>{saving ? "Saving…" : "Save preferences"}</button></div>
              </form>

              <section className="settings-card">
                <div className="settings-card-heading">
                  <span className="settings-icon">⌘</span>
                  <div><h2>AI system configuration</h2><p>Runtime configuration managed by your JANGO server administrator.</p></div>
                </div>
                <div className="settings-grid">
                  <div className="settings-readonly"><span>Active provider</span><strong>{settings.ai_provider}</strong></div>
                  <div className="settings-readonly"><span>Configured model</span><strong>{settings.ai_model}</strong></div>
                </div>
                <p className="settings-hint">Provider credentials and API keys are kept on the backend and are never displayed here.</p>
              </section>

              <form className="settings-card" onSubmit={savePassword}>
                <div className="settings-card-heading">
                  <span className="settings-icon">⌑</span>
                  <div><h2>Change password</h2><p>Confirm your current password before setting a new one.</p></div>
                </div>
                <div className="settings-grid settings-grid-password">
                  <label className="settings-field"><span>Current password</span><input type="password" autoComplete="current-password" value={passwords.current_password} onChange={(e) => setPasswords((p) => ({ ...p, current_password: e.target.value }))} required /></label>
                  <label className="settings-field"><span>New password</span><input type="password" autoComplete="new-password" minLength={8} value={passwords.new_password} onChange={(e) => setPasswords((p) => ({ ...p, new_password: e.target.value }))} required /><small>At least 8 characters.</small></label>
                  <label className="settings-field"><span>Confirm new password</span><input type="password" autoComplete="new-password" minLength={8} value={passwords.confirm} onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))} required /></label>
                </div>
                <div className="settings-actions"><button className="settings-primary" type="submit" disabled={changingPassword}>{changingPassword ? "Updating…" : "Update password"}</button></div>
              </form>

              <section className="settings-card settings-appearance">
                <div className="settings-card-heading">
                  <span className="settings-icon">◐</span>
                  <div><h2>Appearance</h2><p>Current workspace theme.</p></div>
                </div>
                <div className="settings-readonly"><span>Theme</span><strong>Gold & Silver</strong></div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
