import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getDocuments, updateStatus } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import VersionHistory from "./VersionHistory";

const DOC_TYPES = ["", "BRD", "FSD", "SRS", "User Manual", "Product Brochure"];
const STATUSES = ["", "draft", "in_review", "approved", "rejected"];

const STATUS_COLORS = {
  draft: { bg: "#f3f4f6", text: "#6b7280" },
  in_review: { bg: "#fffbeb", text: "#d97706" },
  approved: { bg: "#f0fdf4", text: "#16a34a" },
  rejected: { bg: "#fef2f2", text: "#dc2626" },
  completed: { bg: "#f0fdf4", text: "#16a34a" },
};

const STATUS_TRANSITIONS = {
  draft: { label: "Send for Review", next: "in_review" },
  in_review: null, // two options — handled specially
  rejected: { label: "Reset to Draft", next: "draft" },
};

function formatDate(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DocHistory({ refreshTrigger, addToast, onLoadVersion }) {
  const { currentProject, authHeaders } = useAuth();
  const navigate = useNavigate();
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(null);
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [search, setSearch] = useState("");
  const [pendingSearch, setPendingSearch] = useState("");
  const [versionGroupId, setVersionGroupId] = useState(null);

  async function fetchDocs() {
    setError(null);
    try {
      const data = await getDocuments({
        doc_type: filterType || undefined,
        status: filterStatus || undefined,
        search: search || undefined,
        project_id: currentProject?.id || undefined,
      }, authHeaders);
      setDocs(data);
    } catch {
      setError("Could not load history");
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDocs();
  }, [refreshTrigger, filterType, filterStatus, search, currentProject]); // eslint-disable-line react-hooks/exhaustive-deps

  function submitSearch(e) {
    e.preventDefault();
    setSearch(pendingSearch);
  }

  async function handleStatusChange(doc, nextStatus) {
    try {
      await updateStatus(doc.id, nextStatus, authHeaders);
      setDocs((prev) =>
        prev.map((d) => (d.id === doc.id ? { ...d, status: nextStatus } : d))
      );
      addToast(`Status → ${nextStatus.replace("_", " ")}`, "success");
    } catch {
      addToast("Failed to update status", "error");
    }
  }

  function StatusBadge({ status }) {
    const colors = STATUS_COLORS[status] || STATUS_COLORS.draft;
    return (
      <span
        className="status-pill"
        style={{ background: colors.bg, color: colors.text }}
      >
        {status.replace("_", " ")}
      </span>
    );
  }

  function StatusButtons({ doc }) {
    const s = doc.status;
    if (s === "draft") {
      return (
        <button
          className="history-action-btn"
          onClick={() => handleStatusChange(doc, "in_review")}
        >
          Send for Review
        </button>
      );
    }
    if (s === "in_review") {
      return (
        <>
          <button
            className="history-action-btn approve-btn"
            onClick={() => handleStatusChange(doc, "approved")}
          >
            Approve
          </button>
          <button
            className="history-action-btn reject-btn"
            onClick={() => handleStatusChange(doc, "rejected")}
          >
            Reject
          </button>
        </>
      );
    }
    if (s === "rejected") {
      return (
        <button
          className="history-action-btn"
          onClick={() => handleStatusChange(doc, "draft")}
        >
          Reset to Draft
        </button>
      );
    }
    return null;
  }

  return (
    <>
      {versionGroupId && (
        <VersionHistory
          groupId={versionGroupId}
          onClose={() => setVersionGroupId(null)}
        />
      )}

      <div className="card">
        <div className="card-title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>
            Document History
            {currentProject && (
              <span className="project-code-badge" style={{ marginLeft: 10, fontSize: 12 }}>
                {currentProject.code}
              </span>
            )}
          </span>
          {currentProject && (
            <button
              className="btn-link"
              style={{ fontSize: 12 }}
              onClick={() => navigate(`/projects/${currentProject.id}/settings`)}
            >
              Project Settings
            </button>
          )}
        </div>

        {/* Search + filters */}
        <div className="history-filters">
          <form className="history-search-form" onSubmit={submitSearch}>
            <input
              type="text"
              placeholder="Search instructions…"
              value={pendingSearch}
              onChange={(e) => setPendingSearch(e.target.value)}
              className="history-search-input"
            />
            <button type="submit" className="btn btn-secondary history-search-btn">
              Search
            </button>
            {(pendingSearch || search) && (
              <button
                type="button"
                className="btn btn-secondary history-search-btn"
                onClick={() => { setPendingSearch(""); setSearch(""); }}
              >
                ×
              </button>
            )}
          </form>
          <div className="history-filter-row">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="history-filter-select"
            >
              <option value="">All types</option>
              {DOC_TYPES.slice(1).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="history-filter-select"
            >
              <option value="">All statuses</option>
              {STATUSES.slice(1).map((s) => (
                <option key={s} value={s}>{s.replace("_", " ")}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="history-scroll">
          {error && <div className="error-message">{error}</div>}
          {!error && docs.length === 0 && (
            <div className="history-empty">No documents found.</div>
          )}
          <div className="history-list">
            {docs.map((doc) => (
              <div key={doc.id} className="history-item history-item-v2">
                <div className="history-item-top">
                  <span className="history-badge">{doc.doc_type}</span>
                  <StatusBadge status={doc.status} />
                  <span className="history-version">{doc.version}</span>
                  {doc.project_id && !currentProject && (
                    <span className="project-code-badge" style={{ fontSize: 11 }}>
                      #{doc.project_id}
                    </span>
                  )}
                </div>
                <div className="history-instructions">
                  {doc.instructions.length > 100
                    ? doc.instructions.slice(0, 100) + "…"
                    : doc.instructions}
                </div>
                <div className="history-meta-row">
                  <span className="history-date">{formatDate(doc.created_at)}</span>
                  <div className="history-item-actions">
                    <button
                      className="history-action-btn"
                      title="Load this document into the left pane"
                      onClick={() => onLoadVersion(doc)}
                    >
                      Load
                    </button>
                    {doc.document_group_id && (
                      <button
                        className="history-action-btn"
                        onClick={() => setVersionGroupId(doc.document_group_id)}
                      >
                        Version History
                      </button>
                    )}
                    <StatusButtons doc={doc} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
