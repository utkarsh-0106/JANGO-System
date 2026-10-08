import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../api/error";
import authAI from "../assets/auth-ai.png";

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setSubmitting(true);

    try {
      await register(username, email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Registration failed. Please try again."
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
            BUILD YOUR KNOWLEDGE BASE
          </span>

          <h2>
            Turn documents
            <br />
            <span>into intelligence.</span>
          </h2>

          <p>
            Create your private AI workspace and
            let Jango understand the information
            that matters to you.
          </p>

          <div className="showcase-flow">
            <span>Upload</span>
            <b>→</b>
            <span>Understand</span>
            <b>→</b>
            <span>Ask</span>
          </div>
        </div>

      </div>

      <div className="auth-card">
        <div className="brand">JANGO RAG</div>

        <h1>Create account</h1>
        <p className="subtitle">
          Build your private document knowledge base.
        </p>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <label>Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Your username"
            minLength={3}
            required
          />

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
            placeholder="Minimum 8 characters"
            minLength={8}
            required
          />

          <button type="submit" disabled={submitting}>
            {submitting ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
