import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { generateBulk } from "../services/api";

const DOC_TYPES = [
  "Business Requirements Document",
  "Functional Specification Document",
  "Software Requirements Specification",
  "User Manual",
  "Product Brochure",
];

const FORMAT_OPTIONS = [
  { value: "docx", label: "Word (.docx)" },
  { value: "pdf", label: "PDF (.pdf)" },
  { value: "md", label: "Markdown (.md)" },
];

export default function BulkGenerateModal({ onClose, addToast }) {
  const { authHeaders } = useAuth();
  const [selected, setSelected] = useState(new Set());
  const [projectName, setProjectName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [exportFormat, setExportFormat] = useState("docx");
  const [loading, setLoading] = useState(false);

  function toggle(type) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(DOC_TYPES));
  }

  function clearAll() {
    setSelected(new Set());
  }

  async function handleGenerate() {
    if (selected.size === 0) {
      addToast("Select at least one document type", "error");
      return;
    }
    if (!projectName.trim()) {
      addToast("Enter a project name", "error");
      return;
    }
    if (!instructions.trim()) {
      addToast("Enter generation instructions", "error");
      return;
    }

    setLoading(true);
    try {
      const { blob, filename } = await generateBulk(
        {
          project_name: projectName.trim(),
          doc_types: [...selected],
          instructions: instructions.trim(),
          export_format: exportFormat,
        },
        authHeaders
      );

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      addToast(`${selected.size} document(s) generated — downloading zip`, "success");
      onClose();
    } catch (err) {
      addToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box bulk-modal">
        <div className="modal-header">
          <h3>📦 Bulk Document Generation</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="bulk-body">
          <div className="form-group">
            <label>Project Name</label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="e.g. Acme CRM v2.0"
            />
          </div>

          <div className="form-group">
            <label>
              Document Types
              <span className="bulk-actions">
                <button type="button" className="btn-link" onClick={selectAll}>All</button>
                <button type="button" className="btn-link" onClick={clearAll}>None</button>
              </span>
            </label>
            <div className="bulk-checklist">
              {DOC_TYPES.map((t) => (
                <label key={t} className="bulk-check-item">
                  <input
                    type="checkbox"
                    checked={selected.has(t)}
                    onChange={() => toggle(t)}
                  />
                  {t}
                </label>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Instructions (applied to all documents)</label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={4}
              placeholder="Describe the project context, requirements, audience…"
            />
          </div>

          <div className="form-group">
            <label>Export Format</label>
            <div className="format-radio-group">
              {FORMAT_OPTIONS.map(({ value, label }) => (
                <label key={value} className="format-radio">
                  <input
                    type="radio"
                    name="bulk-format"
                    value={value}
                    checked={exportFormat === value}
                    onChange={() => setExportFormat(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleGenerate} disabled={loading}>
            {loading
              ? `Generating ${selected.size} doc(s)…`
              : `Generate ${selected.size} doc(s) → .zip`}
          </button>
        </div>
      </div>
    </div>
  );
}
