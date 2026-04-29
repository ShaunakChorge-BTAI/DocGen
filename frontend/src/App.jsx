import { useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import DocForm from "./components/DocForm";
import DocHistory from "./components/DocHistory";
import AdminPanel from "./components/AdminPanel";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import LoginPage from "./components/LoginPage";
import NotificationBell from "./components/NotificationBell";
import BulkGenerateModal from "./components/BulkGenerateModal";
import ProjectSelector from "./components/ProjectSelector";
import ProjectSettings from "./components/ProjectSettings";
import ToastContainer, { useToast } from "./components/Toast";
import "./styles/theme.css";

// ── Authenticated layout with nav ─────────────────────────────────────────────

function AppShell() {
  const { user, logout, isAdmin, isApprover } = useAuth();
  const [toasts, setToasts] = useState([]);
  const addToast = useToast(toasts, setToasts);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showBulk, setShowBulk] = useState(false);
  const [selectedHistoryDoc, setSelectedHistoryDoc] = useState(null);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  function handleGenerated() {
    setRefreshTrigger((n) => n + 1);
  }

  function handleLoadVersion(doc) {
    setSelectedHistoryDoc(doc);
  }

  return (
    <>
      <header className="app-header">
        <div className="header-brand">
          <span style={{ fontSize: 22 }}>📄</span>
          <h1>DocGen</h1>
        </div>

        <nav className="header-nav">
          <NavLink
            to="/"
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            end
          >
            Generate
          </NavLink>
          {isApprover && (
            <NavLink
              to="/analytics"
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            >
              Analytics
            </NavLink>
          )}
          {isAdmin && (
            <NavLink
              to="/admin"
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            >
              Admin
            </NavLink>
          )}
          <button
            className="nav-link btn-link"
            onClick={() => setShowBulk(true)}
            title="Bulk generate multiple document types at once"
          >
            Bulk Generate
          </button>
        </nav>

        <div className="header-right">
          <ProjectSelector addToast={addToast} />
          <NotificationBell />
          <span className="header-user" title={user?.email}>
            {user?.name || user?.email}
            <span className="header-role">{user?.role}</span>
          </span>
          <button className="btn-link header-logout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="app-body">
        <Routes>
          <Route
            path="/"
            element={
              <>
                <DocForm
                  key={selectedHistoryDoc?.id ?? "default"}
                  onGenerated={handleGenerated}
                  addToast={addToast}
                  initialDocType={selectedHistoryDoc?.doc_type}
                  initialInstructions={selectedHistoryDoc?.instructions}
                  initialGroupId={selectedHistoryDoc?.document_group_id}
                  historySelectionKey={selectedHistoryDoc?.id ?? null}
                />
                <DocHistory
                  refreshTrigger={refreshTrigger}
                  addToast={addToast}
                  onLoadVersion={handleLoadVersion}
                />
              </>
            }
          />
          {isApprover && (
            <Route
              path="/analytics"
              element={<AnalyticsDashboard addToast={addToast} />}
            />
          )}
          {isAdmin && (
            <Route
              path="/admin"
              element={<AdminPanel addToast={addToast} />}
            />
          )}
          <Route
            path="/projects/:projectId/settings"
            element={<ProjectSettings addToast={addToast} />}
          />
          {/* Fallback — redirect unauthorized access back home */}
          <Route path="*" element={<RedirectHome />} />
        </Routes>
      </main>

      {showBulk && (
        <BulkGenerateModal onClose={() => setShowBulk(false)} addToast={addToast} />
      )}

      <ToastContainer toasts={toasts} />
    </>
  );
}

function RedirectHome() {
  const navigate = useNavigate();
  // Redirect on render — simple, no useEffect needed
  navigate("/", { replace: true });
  return null;
}

// ── Root: gate on auth ─────────────────────────────────────────────────────────

function AuthGate() {
  const { user } = useAuth();
  const [toasts, setToasts] = useState([]);
  const addToast = useToast(toasts, setToasts);

  if (!user) {
    return (
      <>
        <LoginPage addToast={addToast} />
        <ToastContainer toasts={toasts} />
      </>
    );
  }

  return <AppShell />;
}

// ── App ────────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <AuthGate />
    </BrowserRouter>
  );
}
