import { Link, useLocation } from "react-router-dom";
import logo from "../assets/logo.png";
export default function Sidebar() {
  const location = useLocation();

  const isDashboard = location.pathname === "/dashboard";
  const isAnalytics = location.pathname === "/analytics";

  return (
    <aside className="jango-sidebar">

      {/* Brand */}
      <div className="sidebar-brand">
        <Link to="/dashboard">
          <img src={logo} alt="Jango" />

          <div className="sidebar-brand-text">
            <strong>JANGO</strong>
            <span>PRIVATE AI</span>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">

        <p className="sidebar-section-title">
          WORKSPACE
        </p>

        <Link
          to="/dashboard"
          className={`sidebar-link ${
            isDashboard ? "active" : ""
          }`}
        >
          <span className="sidebar-icon">⌂</span>
          <span>Dashboard</span>
        </Link>

        <Link
          to="/dashboard#documents"
          className="sidebar-link"
        >
          <span className="sidebar-icon">▤</span>
          <span>Documents</span>
        </Link>

        <Link
          to="/analytics"
          className={`sidebar-link ${isAnalytics ? "active" : ""}`}
        >
          <span className="sidebar-icon">◫</span>
          <span>Analytics</span>
        </Link>

        <button
          className="sidebar-link sidebar-disabled"
          type="button"
          disabled
        >
          <span className="sidebar-icon">⚙</span>
          <span>Settings</span>
          <small>SOON</small>
        </button>

      </nav>

      {/* Bottom user */}
      <div className="sidebar-user">

        <div className="sidebar-user-avatar">
          U
        </div>

        <div className="sidebar-user-info">
          <strong>Enterprise User</strong>
          <span>Private Workspace</span>
        </div>

      </div>

    </aside>
  );
}
