import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import {
  listTemplates, getTemplate, updateTemplate,
  getBrandGuide, updateBrandGuide,
  getSystemPrompt, updateSystemPrompt,
  getModelConfig, setModelConfig,
  listUsers, deleteUser,
} from "../services/api";

const TABS = ["Templates", "Brand Guide", "System Prompt", "LLM Settings", "Users"];

// ── Templates tab ──────────────────────────────────────────────────────────────

function TemplatesTab({ authHeaders, addToast }) {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listTemplates(authHeaders)
      .then(setTemplates)
      .catch((e) => addToast(e.message, "error"));
  }, [authHeaders, addToast]);

  async function loadTemplate(name) {
    try {
      const data = await getTemplate(name, authHeaders);
      setSelected(data.name);
      setContent(data.content);
    } catch (e) {
      addToast(e.message, "error");
    }
  }

  async function save() {
    setSaving(true);
    try {
      await updateTemplate(selected, content, authHeaders);
      addToast(`Template "${selected}" saved`, "success");
    } catch (e) {
      addToast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-split">
      <aside className="admin-file-list">
        <h4>Templates</h4>
        {templates.map((t) => (
          <button
            key={t.name}
            className={`file-list-item${selected === t.name ? " active" : ""}`}
            onClick={() => loadTemplate(t.name)}
          >
            {t.name}
          </button>
        ))}
      </aside>
      <div className="admin-editor">
        {selected ? (
          <>
            <div className="admin-editor-header">
              <span className="admin-filename">{selected}.md</span>
              <button className="btn-primary" onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
            <textarea
              className="admin-textarea"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
            />
          </>
        ) : (
          <p className="admin-placeholder">← Select a template to edit</p>
        )}
      </div>
    </div>
  );
}

// ── Single-file editor (Brand Guide / System Prompt) ───────────────────────────

function FileEditor({ label, load, save, addToast, authHeaders }) {
  const [content, setContent] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load(authHeaders)
      .then((d) => { setContent(d.content); setLoaded(true); })
      .catch((e) => addToast(e.message, "error"));
  }, [load, authHeaders, addToast]);

  async function handleSave() {
    setSaving(true);
    try {
      await save(content, authHeaders);
      addToast(`${label} saved`, "success");
    } catch (e) {
      addToast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return <p className="admin-placeholder">Loading…</p>;

  return (
    <div className="admin-editor" style={{ flex: 1 }}>
      <div className="admin-editor-header">
        <span className="admin-filename">{label}</span>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      <textarea
        className="admin-textarea"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
      />
    </div>
  );
}

// ── LLM Settings tab ───────────────────────────────────────────────────────────

function LLMTab({ authHeaders, addToast }) {
  const [config, setConfig] = useState(null);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getModelConfig(authHeaders)
      .then((d) => { setConfig(d); setSelected(d.current); })
      .catch((e) => addToast(e.message, "error"));
  }, [authHeaders, addToast]);

  async function save() {
    setSaving(true);
    try {
      await setModelConfig(selected, authHeaders);
      addToast(`Model set to "${selected}"`, "success");
    } catch (e) {
      addToast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  if (!config) return <p className="admin-placeholder">Loading…</p>;

  return (
    <div className="admin-llm">
      <h4>Active LLM Model</h4>
      <p className="admin-hint">
        Env default: <code>{config.env_default}</code>. Changes take effect immediately — no
        restart required.
      </p>
      <div className="llm-model-row">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {config.available.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <button className="btn-primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Apply"}
        </button>
      </div>
    </div>
  );
}

// ── Users tab ──────────────────────────────────────────────────────────────────

function UsersTab({ authHeaders, addToast }) {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);

  const load = useCallback(() => {
    listUsers(authHeaders)
      .then(setUsers)
      .catch((e) => addToast(e.message, "error"));
  }, [authHeaders, addToast]);

  useEffect(load, [load]);

  async function handleDelete(id, name) {
    if (!confirm(`Delete user "${name}"? This cannot be undone.`)) return;
    try {
      await deleteUser(id, authHeaders);
      addToast(`User "${name}" deleted`, "success");
      load();
    } catch (e) {
      addToast(e.message, "error");
    }
  }

  const ROLE_COLOR = { admin: "#c0392b", approver: "#2980b9", reviewer: "#27ae60", author: "#7f8c8d" };

  return (
    <div className="admin-users">
      <h4>Registered Users ({users.length})</h4>
      <table className="admin-table">
        <thead>
          <tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th><th></th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.name}</td>
              <td>{u.email}</td>
              <td>
                <span
                  className="role-badge"
                  style={{ background: ROLE_COLOR[u.role] || "#95a5a6" }}
                >
                  {u.role}
                </span>
              </td>
              <td>{new Date(u.created_at).toLocaleDateString()}</td>
              <td>
                {u.id !== me?.id && (
                  <button
                    className="btn-danger-sm"
                    onClick={() => handleDelete(u.id, u.name)}
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main AdminPanel ────────────────────────────────────────────────────────────

export default function AdminPanel({ addToast }) {
  const { authHeaders } = useAuth();
  const [activeTab, setActiveTab] = useState("Templates");

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h2>⚙️ Admin Panel</h2>
        <p>Manage templates, brand guidelines, LLM settings, and users.</p>
      </div>

      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t}
            className={activeTab === t ? "active" : ""}
            onClick={() => setActiveTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="admin-content">
        {activeTab === "Templates" && (
          <TemplatesTab authHeaders={authHeaders} addToast={addToast} />
        )}
        {activeTab === "Brand Guide" && (
          <FileEditor
            label="brand-guide.md"
            load={getBrandGuide}
            save={updateBrandGuide}
            authHeaders={authHeaders}
            addToast={addToast}
          />
        )}
        {activeTab === "System Prompt" && (
          <FileEditor
            label="system-prompt.md"
            load={getSystemPrompt}
            save={updateSystemPrompt}
            authHeaders={authHeaders}
            addToast={addToast}
          />
        )}
        {activeTab === "LLM Settings" && (
          <LLMTab authHeaders={authHeaders} addToast={addToast} />
        )}
        {activeTab === "Users" && (
          <UsersTab authHeaders={authHeaders} addToast={addToast} />
        )}
      </div>
    </div>
  );
}
