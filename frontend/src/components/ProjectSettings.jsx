import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  getProject, updateProject,
  getProjectMembers, addProjectMember, removeProjectMember,
  uploadProjectLogo, listUsers,
} from "../services/api";

const MEMBER_ROLES = ["author", "reviewer", "approver", "owner"];

export default function ProjectSettings({ addToast }) {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { authHeaders, user } = useAuth();

  const [project, setProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [tab, setTab] = useState("info");
  const [loading, setLoading] = useState(true);

  // Info tab
  const [infoForm, setInfoForm] = useState({ name: "", client_name: "", description: "", preferred_model: "" });
  const [infoSaving, setInfoSaving] = useState(false);

  // Members tab
  const [allUsers, setAllUsers] = useState([]);
  const [addForm, setAddForm] = useState({ user_id: "", role: "author" });
  const [addSaving, setAddSaving] = useState(false);

  // Logos tab
  const [companyFile, setCompanyFile] = useState(null);
  const [clientFile, setClientFile] = useState(null);
  const [logoSaving, setLogoSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadData() {
    setLoading(true);
    try {
      const [proj, mems] = await Promise.all([
        getProject(parseInt(projectId), authHeaders),
        getProjectMembers(parseInt(projectId), authHeaders),
      ]);
      setProject(proj);
      setInfoForm({
        name: proj.name || "",
        client_name: proj.client_name || "",
        description: proj.description || "",
        preferred_model: proj.preferred_model || "",
      });
      setMembers(mems);
    } catch (err) {
      addToast(err.message || "Failed to load project", "error");
      navigate("/");
    } finally {
      setLoading(false);
    }
  }

  async function loadUsers() {
    try {
      const users = await listUsers(authHeaders);
      setAllUsers(users);
    } catch {
      // admin-only endpoint — non-admins won't have this
    }
  }

  useEffect(() => {
    if (tab === "members") loadUsers();
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveInfo(e) {
    e.preventDefault();
    setInfoSaving(true);
    try {
      const updated = await updateProject(parseInt(projectId), infoForm, authHeaders);
      setProject(updated);
      addToast("Project updated", "success");
    } catch (err) {
      addToast(err.message || "Update failed", "error");
    } finally {
      setInfoSaving(false);
    }
  }

  async function handleAddMember(e) {
    e.preventDefault();
    if (!addForm.user_id) return;
    setAddSaving(true);
    try {
      const member = await addProjectMember(
        parseInt(projectId),
        { user_id: parseInt(addForm.user_id), role: addForm.role },
        authHeaders
      );
      setMembers((prev) => {
        const idx = prev.findIndex((m) => m.user_id === member.user_id);
        return idx >= 0 ? prev.map((m, i) => (i === idx ? member : m)) : [...prev, member];
      });
      setAddForm({ user_id: "", role: "author" });
      addToast("Member added", "success");
    } catch (err) {
      addToast(err.message || "Failed to add member", "error");
    } finally {
      setAddSaving(false);
    }
  }

  async function handleRemoveMember(memberId, memberUserId) {
    if (!confirm("Remove this member from the project?")) return;
    try {
      await removeProjectMember(parseInt(projectId), memberUserId, authHeaders);
      setMembers((prev) => prev.filter((m) => m.user_id !== memberUserId));
      addToast("Member removed", "success");
    } catch (err) {
      addToast(err.message || "Failed to remove member", "error");
    }
  }

  async function uploadLogos(e) {
    e.preventDefault();
    if (!companyFile && !clientFile) return;
    setLogoSaving(true);
    try {
      if (companyFile) {
        await uploadProjectLogo(parseInt(projectId), "company", companyFile, authHeaders);
      }
      if (clientFile) {
        await uploadProjectLogo(parseInt(projectId), "client", clientFile, authHeaders);
      }
      addToast("Logo(s) uploaded — they will appear on new documents", "success");
      setCompanyFile(null);
      setClientFile(null);
    } catch (err) {
      addToast(err.message || "Upload failed", "error");
    } finally {
      setLogoSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
        Loading project…
      </div>
    );
  }

  return (
    <div className="card" style={{ maxWidth: 720 }}>
      <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn-link" onClick={() => navigate("/")} style={{ fontSize: 18 }}>←</button>
        <span className="project-code-badge" style={{ fontSize: 13 }}>{project?.code}</span>
        {project?.name} — Settings
      </div>

      {/* Tab bar */}
      <div className="settings-tabs">
        {["info", "members", "logos"].map((t) => (
          <button
            key={t}
            className={`settings-tab ${tab === t ? "active" : ""}`}
            onClick={() => setTab(t)}
          >
            {{ info: "Project Info", members: "Team Members", logos: "Logos" }[t]}
          </button>
        ))}
      </div>

      {/* Info tab */}
      {tab === "info" && (
        <form onSubmit={saveInfo} style={{ marginTop: 20 }}>
          <div className="form-group">
            <label className="form-label">Project Name</label>
            <input value={infoForm.name} onChange={(e) => setInfoForm((f) => ({ ...f, name: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label className="form-label">Client Name</label>
            <input value={infoForm.client_name} onChange={(e) => setInfoForm((f) => ({ ...f, client_name: e.target.value }))} placeholder="Acme Corp" />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea value={infoForm.description} onChange={(e) => setInfoForm((f) => ({ ...f, description: e.target.value }))} rows={3} />
          </div>
          <div className="form-group">
            <label className="form-label">Preferred LLM Model <span className="optional">(overrides admin default)</span></label>
            <input value={infoForm.preferred_model} onChange={(e) => setInfoForm((f) => ({ ...f, preferred_model: e.target.value }))} placeholder="e.g. llama3 or mistral" />
          </div>
          <button type="submit" className="btn btn-primary" disabled={infoSaving}>
            {infoSaving ? "Saving…" : "Save Changes"}
          </button>
        </form>
      )}

      {/* Members tab */}
      {tab === "members" && (
        <div style={{ marginTop: 20 }}>
          <table className="members-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td>{m.user_name || "—"}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: 12 }}>{m.user_email || "—"}</td>
                  <td><span className="member-role-badge member-role-{m.role}">{m.role}</span></td>
                  <td>
                    {m.user_id !== user?.id && (
                      <button
                        className="btn-link danger-link"
                        onClick={() => handleRemoveMember(m.id, m.user_id)}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {allUsers.length > 0 && (
            <form onSubmit={handleAddMember} className="add-member-form">
              <div className="form-label" style={{ marginBottom: 8, fontWeight: 600 }}>Add Member</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <select
                  value={addForm.user_id}
                  onChange={(e) => setAddForm((f) => ({ ...f, user_id: e.target.value }))}
                  style={{ flex: 2, minWidth: 180 }}
                >
                  <option value="">Select user…</option>
                  {allUsers
                    .filter((u) => !members.find((m) => m.user_id === u.id))
                    .map((u) => (
                      <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                    ))}
                </select>
                <select
                  value={addForm.role}
                  onChange={(e) => setAddForm((f) => ({ ...f, role: e.target.value }))}
                  style={{ flex: 1, minWidth: 120 }}
                >
                  {MEMBER_ROLES.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <button type="submit" className="btn btn-primary" disabled={!addForm.user_id || addSaving}>
                  {addSaving ? "Adding…" : "Add"}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Logos tab */}
      {tab === "logos" && (
        <form onSubmit={uploadLogos} style={{ marginTop: 20 }}>
          <div className="form-group">
            <label className="form-label">Company Logo</label>
            <label className="file-upload-area">
              <input type="file" accept="image/*" onChange={(e) => setCompanyFile(e.target.files[0] || null)} />
              <span className="upload-icon">🏢</span>
              <span className="upload-text">
                {companyFile ? companyFile.name : "Upload company logo (.png/.jpg, max 2 MB)"}
              </span>
            </label>
            {project?.company_logo_path && !companyFile && (
              <div className="logo-current">Current: {project.company_logo_path.split(/[/\\]/).pop()}</div>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Client Logo</label>
            <label className="file-upload-area">
              <input type="file" accept="image/*" onChange={(e) => setClientFile(e.target.files[0] || null)} />
              <span className="upload-icon">🤝</span>
              <span className="upload-text">
                {clientFile ? clientFile.name : "Upload client logo (.png/.jpg, max 2 MB)"}
              </span>
            </label>
            {project?.client_logo_path && !clientFile && (
              <div className="logo-current">Current: {project.client_logo_path.split(/[/\\]/).pop()}</div>
            )}
          </div>

          <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
            Logos will appear on the title page of documents generated for this project.
          </p>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={logoSaving || (!companyFile && !clientFile)}
          >
            {logoSaving ? "Uploading…" : "Upload Logo(s)"}
          </button>
        </form>
      )}
    </div>
  );
}
