import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import api from "../api/axios";
import Sidebar from "../components/Sidebar";

function formatTokens(value) {
  if (!Number.isFinite(value)) return "0";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function formatCost(value) {
  return `$${Number(value || 0).toFixed(4)}`;
}

function formatLatency(value) {
  if (!value) return "0 ms";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

function shortDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [recent, setRecent] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadAnalytics() {
    setLoading(true);
    setError("");
    try {
      const [summaryResponse, recentResponse] = await Promise.all([
        api.get(`/api/usage/summary?days=${days}`),
        api.get("/api/usage/recent?limit=10"),
      ]);
      setSummary(summaryResponse.data);
      setRecent(recentResponse.data);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      setError(
        status === 401
          ? "Your session has expired. Please log in again."
          : detail || "Unable to load AI usage analytics. Make sure the JANGO backend is running."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalytics();
  }, [days]);

  const maxDailyTokens = useMemo(
    () => Math.max(...(summary?.daily || []).map((item) => item.tokens), 1),
    [summary]
  );

  const maxModelTokens = useMemo(
    () => Math.max(...(summary?.models || []).map((item) => item.tokens), 1),
    [summary]
  );

  return (
    <div className="dashboard jango-dashboard dashboard-shell analytics-shell">
      <Sidebar />

      <div className="dashboard-main-area">
        <main className="dashboard-content analytics-content">
          <header className="analytics-header">
            <div>
              <p className="eyebrow">AI OBSERVABILITY</p>
              <h1>AI Usage & Cost</h1>
              <p>
                Track RAG requests, token consumption, model usage, latency and estimated AI cost.
              </p>
            </div>

            <div className="analytics-header-actions">
              <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
<Link to="/dashboard" className="back-button">← Dashboard</Link>
            </div>
          </header>

          {error && <div className="alert alert-error"><span>⚠</span>{error}</div>}

          {loading ? (
            <div className="analytics-loading"><div className="spinner" /><p>Loading AI usage...</p></div>
          ) : (
            <>
              <section className="usage-stat-grid">
                <div className="usage-stat-card">
                  <span>AI Requests</span>
                  <strong>{summary?.total_requests || 0}</strong>
                  <small>{summary?.successful_requests || 0} successful</small>
                </div>
                <div className="usage-stat-card usage-stat-accent">
                  <span>Total Tokens</span>
                  <strong>{formatTokens(summary?.total_tokens || 0)}</strong>
                  <small>{formatTokens(summary?.input_tokens || 0)} in · {formatTokens(summary?.output_tokens || 0)} out</small>
                </div>
                <div className="usage-stat-card">
                  <span>Estimated Cost</span>
                  <strong>{formatCost(summary?.estimated_cost_usd || 0)}</strong>
                  <small>Based on configured provider rates</small>
                </div>
                <div className="usage-stat-card">
                  <span>Avg. AI Latency</span>
                  <strong>{formatLatency(summary?.average_latency_ms || 0)}</strong>
                  <small>LLM generation time</small>
                </div>
              </section>

              <section className="analytics-panel usage-chart-panel">
                <div className="analytics-panel-header">
                  <div>
                    <p className="eyebrow">ACTIVITY</p>
                    <h2>Token usage</h2>
                  </div>
                  <span className="analytics-badge">{days} days</span>
                </div>

                <div className="usage-bars" aria-label="Daily token usage chart">
                  {(summary?.daily || []).map((item) => (
                    <div className="usage-bar-column" key={item.date} title={`${item.date}: ${item.tokens} tokens`}>
                      <div className="usage-bar-track">
                        <div className="usage-bar-fill" style={{ height: `${Math.max((item.tokens / maxDailyTokens) * 100, item.tokens ? 8 : 2)}%` }} />
                      </div>
                      <span>{shortDate(item.date)}</span>
                    </div>
                  ))}
                </div>
              </section>

              <div className="analytics-two-column">
                <section className="analytics-panel">
                  <div className="analytics-panel-header">
                    <div>
                      <p className="eyebrow">MODELS</p>
                      <h2>Usage by model</h2>
                    </div>
                  </div>

                  {summary?.models?.length ? (
                    <div className="model-usage-list">
                      {summary.models.map((item) => (
                        <div className="model-usage-row" key={`${item.provider}/${item.model}`}>
                          <div className="model-usage-heading">
                            <div>
                              <strong>{item.model}</strong>
                              <span>{item.provider} · {item.requests} requests</span>
                            </div>
                            <b>{formatTokens(item.tokens)}</b>
                          </div>
                          <div className="model-progress"><span style={{ width: `${Math.max((item.tokens / maxModelTokens) * 100, 3)}%` }} /></div>
                          <small>{formatCost(item.cost_usd)}</small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="analytics-empty">No AI requests recorded yet. Ask Jango a question to start tracking.</div>
                  )}
                </section>

                <section className="analytics-panel">
                  <div className="analytics-panel-header">
                    <div>
                      <p className="eyebrow">PRICING</p>
                      <h2>Cost configuration</h2>
                    </div>
                  </div>

                  <div className="pricing-card">
                    <div><span>Input</span><strong>${Number(summary?.pricing?.input_per_1m_usd || 0).toFixed(2)} / 1M</strong></div>
                    <div><span>Output</span><strong>${Number(summary?.pricing?.output_per_1m_usd || 0).toFixed(2)} / 1M</strong></div>
                  </div>
                  <p className="analytics-note">{summary?.pricing?.note}</p>
                </section>
              </div>

              <section className="analytics-panel recent-usage-panel">
                <div className="analytics-panel-header">
                  <div>
                    <p className="eyebrow">REQUEST LOG</p>
                    <h2>Recent AI requests</h2>
                  </div>
                  <button className="refresh-button" onClick={loadAnalytics}>↻ Refresh</button>
                </div>

                {recent.length ? (
                  <div className="usage-table-wrapper">
                    <table className="usage-table">
                      <thead><tr><th>Model</th><th>Operation</th><th>Tokens</th><th>Latency</th><th>Cost</th><th>Status</th></tr></thead>
                      <tbody>
                        {recent.map((item) => (
                          <tr key={item.id}>
                            <td><strong>{item.model}</strong><small>{item.provider}</small></td>
                            <td>{item.operation.replaceAll("_", " ")}</td>
                            <td>{formatTokens(item.total_tokens)} {item.tokens_estimated ? <em>est.</em> : null}</td>
                            <td>{formatLatency(item.latency_ms)}</td>
                            <td>{formatCost(item.estimated_cost_usd)}</td>
                            <td><span className={`usage-status ${item.status}`}>{item.status}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="analytics-empty">No recent AI requests.</div>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
