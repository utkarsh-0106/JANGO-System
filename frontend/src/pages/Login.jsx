import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../api/error";
import authAI from "../assets/auth-ai.png";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setSubmitting(true);

    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Login failed. Please check your credentials."
        )
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">

      <div className="auth-showcase">

        <div className="showcase-brand">
          <span>✦</span>
          <div>
            <strong>JANGO</strong>
            <small>PRIVATE AI</small>
          </div>
        </div>

        <div className="showcase-visual">
          <div className="showcase-orbit orbit-one"></div>
          <div className="showcase-orbit orbit-two"></div>

          <img
            src={authAI}
            alt="Jango private AI"
          />

          <div className="floating-node node-one">
            <span>✦</span>
            Knowledge
          </div>

          <div className="floating-node node-two">
            <span>◈</span>
            RAG Engine
          </div>

          <div className="floating-node node-three">
            <span>✓</span>
            Private
          </div>
        </div>

        <div className="showcase-copy">
          <span className="showcase-eyebrow">
            PRIVATE INTELLIGENCE
          </span>

          <h2>
            Your documents.
            <br />
            <span>Your intelligence.</span>
          </h2>

          <p>
            Upload your knowledge, ask questions,
            and get intelligent answers grounded
            in your own documents.
          </p>

          <div className="showcase-flow">
            <span>Documents</span>
            <b>→</b>
            <span>Knowledge</span>
            <b>→</b>
            <span>Answers</span>
          </div>
        </div>

      </div>

      <div className="auth-card">
        <div className="brand">JANGO RAG</div>

        <h1>Welcome back</h1>
        <p className="subtitle">
          Sign in to your document knowledge base.
        </p>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />

          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />

          <button type="submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="auth-footer">
          Don't have an account?{" "}
          <Link to="/register">Create account</Link>
        </p>
      </div>
    </div>
  );
}
