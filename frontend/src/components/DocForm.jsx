import { useState, useRef, useEffect } from "react";
import { previewDoc } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import LoadingSpinner from "./LoadingSpinner";
import PreviewPanel from "./PreviewPanel";
import SnippetsPanel from "./SnippetsPanel";

const DOC_TYPES = ["BRD", "FSD", "SRS", "User Manual", "Product Brochure"];

export default function DocForm({ onGenerated, addToast, initialDocType, initialInstructions, initialGroupId }) {
  const { currentProject, authHeaders } = useAuth();
  const [docType, setDocType] = useState(initialDocType || "BRD");
  const [instructions, setInstructions] = useState(initialInstructions || "");
  const [file, setFile] = useState(null);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null); // { markdown, changedSections }
  const fileInputRef = useRef();
  const instructionsRef = useRef();

  // Ctrl+Enter submits the form
  useEffect(() => {
    function onKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !loading && !preview) {
        e.preventDefault();
        if (instructions.trim()) handleSubmit();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [instructions, loading, preview]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleFileChange(e) {
    const selected = e.target.files[0];
    if (!selected) return;
    const ext = selected.name.split(".").pop().toLowerCase();
    if (!["docx", "pdf"].includes(ext)) {
      setError("Only .docx and .pdf files are accepted.");
      return;
    }
    setError(null);
    setFile(selected);
  }

  function handleReset() {
    setDocType(initialDocType || "BRD");
    setInstructions(initialInstructions || "");
    setFile(null);
    setShowFileUpload(false);
    setError(null);
    setPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function appendSnippet(content) {
    setInstructions((prev) =>
      prev.trim() ? `${prev.trim()}\n\n${content}` : content
    );
    instructionsRef.current?.focus();
  }

  async function handleSubmit(e) {
    if (e) e.preventDefault();
    if (!instructions.trim()) {
      setError("Please enter instructions for the document.");
      return;
    }

    const formData = new FormData();
    formData.append("doc_type", docType);
    formData.append("instructions", instructions.trim());
    if (currentProject?.id) formData.append("project_id", currentProject.id);
    if (file) formData.append("previous_file", file);

    setLoading(true);
    setError(null);
    setPreview(null);

    try {
      const { markdown, changed_sections } = await previewDoc(formData, authHeaders);
      setPreview({ markdown, changedSections: changed_sections });
      addToast("Preview ready — review and confirm to download", "info");
    } catch (err) {
      setError(err.message || "Generation failed. Is Ollama running?");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="card-title">Generate Document</div>
        <LoadingSpinner />
      </div>
    );
  }

  if (preview) {
    return (
      <div className="card">
        <div className="card-title">Generate Document</div>
        <PreviewPanel
          docType={docType}
          instructions={instructions}
          markdown={preview.markdown}
          changedSections={preview.changedSections}
          groupId={initialGroupId || null}
          projectId={currentProject?.id || null}
          onReset={handleReset}
          onGenerated={onGenerated}
          addToast={addToast}
        />
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">Generate Document</div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Document Type</label>
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            {DOC_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">
            Instructions / Change Description
            <span className="optional"> — Ctrl+Enter to generate</span>
          </label>
          <textarea
            ref={instructionsRef}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Describe what you want in this document…"
            rows={6}
          />
        </div>

        <SnippetsPanel
          docType={docType}
          currentInstructions={instructions}
          onAppend={appendSnippet}
          addToast={addToast}
        />

        <div className="form-group" style={{ marginTop: 16 }}>
          <label className="form-label">Previous Version</label>
          {currentProject ? (
            <div className="auto-prev-notice">
              <span className="auto-prev-icon">✓</span>
              Previous version will be loaded automatically from <strong>{currentProject.name}</strong> project history.
              <button
                type="button"
                className="btn-link"
                style={{ marginLeft: 8, fontSize: 12 }}
                onClick={() => setShowFileUpload((v) => !v)}
              >
                {showFileUpload ? "Hide upload" : "Import from external file instead"}
              </button>
            </div>
          ) : null}

          {(!currentProject || showFileUpload) && (
            <label className="file-upload-area" style={{ marginTop: currentProject ? 8 : 0 }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.pdf"
                onChange={handleFileChange}
              />
              <span className="upload-icon">📎</span>
              <span className="upload-text">
                Upload .docx or .pdf — enables diff-aware section updates
              </span>
            </label>
          )}
          {file && (
            <div className="file-selected">
              📄 {file.name}
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
              >
                ×
              </button>
            </div>
          )}
        </div>

        {error && <div className="error-message">{error}</div>}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={!instructions.trim()}
        >
          Generate Preview
        </button>
      </form>
    </div>
  );
}
