import { useState, useEffect } from "react";
import { getSnippets, createSnippet, deleteSnippet, useSnippet } from "../services/api";

export default function SnippetsPanel({ docType, currentInstructions, onAppend, addToast }) {
  const [snippets, setSnippets] = useState([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  useEffect(() => {
    if (open) {
      getSnippets(docType).then(setSnippets).catch(() => {});
    }
  }, [open, docType]);

  async function handleUse(snippet) {
    onAppend(snippet.content);
    await useSnippet(snippet.id).catch(() => {});
    setSnippets((prev) =>
      prev.map((s) => (s.id === snippet.id ? { ...s, usage_count: s.usage_count + 1 } : s))
    );
    addToast("Snippet appended to instructions", "success");
  }

  async function handleSave() {
    if (!newTitle.trim() || !currentInstructions.trim()) return;
    setSaving(true);
    try {
      const created = await createSnippet({
        title: newTitle.trim(),
        content: currentInstructions.trim(),
        doc_type: docType,
      });
      setSnippets((prev) => [created, ...prev]);
      setNewTitle("");
      addToast("Snippet saved", "success");
    } catch {
      addToast("Failed to save snippet", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteSnippet(id);
      setSnippets((prev) => prev.filter((s) => s.id !== id));
      addToast("Snippet deleted", "info");
    } catch {
      addToast("Failed to delete snippet", "error");
    }
  }

  return (
    <div className="snippets-panel">
      <button
        type="button"
        className="snippets-toggle"
        onClick={() => setOpen((o) => !o)}
      >
        <span>Saved Snippets</span>
        <span className="snippets-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="snippets-body">
          {snippets.length === 0 ? (
            <p className="snippets-empty">No snippets yet for {docType}.</p>
          ) : (
            <div className="snippets-list">
              {snippets.map((s) => (
                <div key={s.id} className="snippet-item">
                  <button
                    type="button"
                    className="snippet-use-btn"
                    onClick={() => handleUse(s)}
                    title={s.content}
                  >
                    <span className="snippet-title">{s.title}</span>
                    <span className="snippet-meta">
                      {s.doc_type || "All types"} · used {s.usage_count}×
                    </span>
                  </button>
                  <button
                    type="button"
                    className="snippet-delete-btn"
                    onClick={() => handleDelete(s.id)}
                    title="Delete snippet"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {currentInstructions.trim() && (
            <div className="snippet-save-row">
              <input
                type="text"
                placeholder="Snippet name…"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="snippet-name-input"
              />
              <button
                type="button"
                className="btn btn-secondary snippet-save-btn"
                onClick={handleSave}
                disabled={saving || !newTitle.trim()}
              >
                {saving ? "Saving…" : "Save current instructions"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
