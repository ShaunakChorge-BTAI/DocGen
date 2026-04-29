import { useState, useEffect, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getProjects, createProject } from "../services/api";

export default function ProjectSelector({ addToast }) {
  const { currentProject, setCurrentProject, authHeaders } = useAuth();
  const [projects, setProjects] = useState([]);
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", client_name: "", description: "" });
  const [saving, setSaving] = useState(false);
  const dropRef = useRef();

  useEffect(() => {
    loadProjects();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function onDocClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick, true);
    return () => document.removeEventListener("mousedown", onDocClick, true);
  }, []);

  async function loadProjects() {
    try {
      const data = await getProjects(authHeaders);
      setProjects(data);
      // If persisted project is no longer in list, clear it
      if (currentProject && !data.find((p) => p.id === currentProject.id)) {
        setCurrentProject(null);
      }
    } catch {
      // silently fail — projects panel may not exist yet
    }
  }

  function selectProject(project) {
    setCurrentProject(project);
    setOpen(false);
    addToast(`Switched to ${project.name}`, "success");
  }

  function clearProject() {
    setCurrentProject(null);
    setOpen(false);
    addToast("Viewing all projects", "info");
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.code.trim() || !form.name.trim()) return;
    setSaving(true);
    try {
      const project = await createProject(
        { ...form, code: form.code.trim().toUpperCase() },
        authHeaders
      );
      setProjects((prev) => [project, ...prev]);
      setCurrentProject(project);
      setShowCreate(false);
      setForm({ code: "", name: "", client_name: "", description: "" });
      addToast(`Project "${project.name}" created`, "success");
    } catch (err) {
      addToast(err.message || "Failed to create project", "error");
    } finally {
      setSaving(false);
    }
  }

  const label = currentProject
    ? `${currentProject.code} — ${currentProject.name}`
    : "All Projects";

  return (
    <div className="project-selector" ref={dropRef}>
      <button
        className="project-selector-btn"
        onClick={() => setOpen((v) => !v)}
        title="Switch project context"
      >
        <span className="project-selector-icon">📁</span>
        <span className="project-selector-label">{label}</span>
        <span className="project-selector-caret">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="project-dropdown">
          <div className="project-dropdown-header">Your Projects</div>

          <button className="project-dropdown-item project-dropdown-all" onClick={clearProject}>
            <span>All Projects</span>
            {!currentProject && <span className="project-check">✓</span>}
          </button>

          {projects.map((p) => (
            <button
              key={p.id}
              className={`project-dropdown-item ${currentProject?.id === p.id ? "active" : ""}`}
              onClick={() => selectProject(p)}
            >
              <span className="project-code-badge">{p.code}</span>
              <span className="project-dropdown-name">{p.name}</span>
              {currentProject?.id === p.id && <span className="project-check">✓</span>}
            </button>
          ))}

          {projects.length === 0 && (
            <div className="project-dropdown-empty">No projects yet</div>
          )}

          <div className="project-dropdown-divider" />
          <button
            className="project-dropdown-item project-dropdown-create"
            onClick={() => { setOpen(false); setShowCreate(true); }}
          >
            + Create New Project
          </button>
        </div>
      )}

      {showCreate && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}>
          <div className="modal-box" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <span>New Project</span>
              <button className="modal-close" onClick={() => setShowCreate(false)}>×</button>
            </div>
            <form onSubmit={handleCreate} className="modal-body">
              <div className="form-group">
                <label className="form-label">Project Code *</label>
                <input
                  value={form.code}
                  onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PROJ001"
                  maxLength={20}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Project Name *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Customer Portal Redesign"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Client Name</label>
                <input
                  value={form.client_name}
                  onChange={(e) => setForm((f) => ({ ...f, client_name: e.target.value }))}
                  placeholder="e.g. Acme Corp"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={2}
                  placeholder="Brief project description"
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? "Creating…" : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
