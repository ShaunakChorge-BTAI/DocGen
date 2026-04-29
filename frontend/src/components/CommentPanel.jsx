import { useState, useEffect } from "react";
import { getComments, addComment, resolveComment } from "../services/api";

export default function CommentPanel({ docId, addToast }) {
  const [comments, setComments] = useState([]);
  const [section, setSection] = useState("General");
  const [text, setText] = useState("");
  const [author, setAuthor] = useState("User");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (docId) {
      getComments(docId).then(setComments).catch(() => {});
    }
  }, [docId]);

  async function handleAdd(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const created = await addComment(docId, {
        section_name: section,
        comment_text: text.trim(),
        author: author.trim() || "User",
      });
      setComments((prev) => [...prev, created]);
      setText("");
      addToast("Comment added", "success");
    } catch {
      addToast("Failed to add comment", "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResolve(id) {
    try {
      await resolveComment(id);
      setComments((prev) =>
        prev.map((c) => (c.id === id ? { ...c, resolved: true } : c))
      );
      addToast("Comment resolved", "info");
    } catch {
      addToast("Failed to resolve comment", "error");
    }
  }

  const active = comments.filter((c) => !c.resolved);
  const resolved = comments.filter((c) => c.resolved);

  function formatDate(iso) {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="comment-panel">
      <form onSubmit={handleAdd} className="comment-form">
        <div className="comment-form-row">
          <input
            type="text"
            placeholder="Your name"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            className="comment-author-input"
          />
          <input
            type="text"
            placeholder="Section (e.g. Scope)"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            className="comment-section-input"
          />
        </div>
        <div className="comment-form-row">
          <textarea
            placeholder="Add a comment…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            className="comment-textarea"
          />
          <button
            type="submit"
            className="btn btn-primary comment-submit-btn"
            disabled={submitting || !text.trim()}
          >
            {submitting ? "…" : "Add"}
          </button>
        </div>
      </form>

      {active.length === 0 && resolved.length === 0 && (
        <p className="comment-empty">No comments yet. Add one above.</p>
      )}

      {active.map((c) => (
        <div key={c.id} className="comment-item">
          <div className="comment-header">
            <span className="comment-author">{c.author}</span>
            <span className="comment-section-tag">{c.section_name}</span>
            <span className="comment-date">{formatDate(c.created_at)}</span>
          </div>
          <div className="comment-text">{c.comment_text}</div>
          <button
            type="button"
            className="comment-resolve-btn"
            onClick={() => handleResolve(c.id)}
          >
            Mark resolved
          </button>
        </div>
      ))}

      {resolved.length > 0 && (
        <details className="resolved-section">
          <summary>{resolved.length} resolved comment{resolved.length !== 1 ? "s" : ""}</summary>
          {resolved.map((c) => (
            <div key={c.id} className="comment-item comment-resolved">
              <div className="comment-header">
                <span className="comment-author">{c.author}</span>
                <span className="comment-section-tag">{c.section_name}</span>
                <span className="comment-date">{formatDate(c.created_at)}</span>
              </div>
              <div className="comment-text">{c.comment_text}</div>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
