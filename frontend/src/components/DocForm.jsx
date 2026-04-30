import { useState, useRef, useEffect, useCallback } from "react";
import { previewDoc, getDocument } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import LoadingSpinner from "./LoadingSpinner";
import PreviewPanel from "./PreviewPanel";
import SnippetsPanel from "./SnippetsPanel";

const DOC_TYPES = ["BRD", "FSD", "SRS", "User Manual", "Product Brochure"];
const STORAGE_KEY = "docgen_preview_state";

function loadPreviewState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function savePreviewState(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage failures
  }
}

function clearPreviewState() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore storage failures
  }
}

export default function DocForm({
  onGenerated,
  addToast,
  initialDocType,
  initialInstructions,
  initialGroupId,
  historySelectionKey,
  selectedHistoryDoc,
  onClearHistorySelection,
}) {
  const { currentProject, authHeaders } = useAuth();

  const stored = loadPreviewState();
  //1. Determine if we are actively clicking a history item right now
  const isHistoryClick = selectedHistoryDoc != null;

  //2. We ONLY restore from sessionStorage if:
  // - We have stored data
  // - We are NOT clicking a history item (history click overrides storage)
  // - The stored data wasnt a history view from a previos session (selectionKey must be null)
  const shouldRestoreState =
    stored &&
    isHistoryClick &&
    (stored.selectionKey == null);

  const [docType, setDocType] = useState(
    shouldRestoreState
      ? stored.docType || initialDocType || "BRD"
      : selectedHistoryDoc?.doc_type || initialDocType || "BRD"
  );
  const [instructions, setInstructions] = useState(
    shouldRestoreState
      ? stored.instructions || initialInstructions || ""
      : selectedHistoryDoc?.instructions || initialInstructions || ""
  );
  const [file, setFile] = useState(null);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(() => {
    if (!shouldRestoreState) return null;
    return {
      mode: stored.mode || "draft",
      markdown: stored.markdown,
      changedSections: stored.changedSections || [],
      docType: stored.docType || initialDocType || "BRD",
      documentId: stored.documentId || null,
      version: stored.version || null,
      filename: stored.filename || null,
      blobUrl: stored.blobUrl || null,
      groupId: stored.groupId || initialGroupId || null,
      projectId: stored.projectId || currentProject?.id || null,
      instructions: stored.instructions || initialInstructions || "",
      status: stored.status || "draft",
      generationTime: stored.generationTime || null,
    };
  });
  const [selectedDocLoading, setSelectedDocLoading] = useState(false);
  const [selectedDocError, setSelectedDocError] = useState(null);
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

  const persistPreviewState = useCallback((nextPreview) => {
    savePreviewState({
      mode: nextPreview.mode || "draft",
      docType: nextPreview.docType || docType,
      instructions: nextPreview.instructions || instructions,
      markdown: nextPreview.markdown,
      changedSections: nextPreview.changedSections || [],
      documentId: nextPreview.documentId || null,
      version: nextPreview.version || null,
      filename: nextPreview.filename || null,
      blobUrl: nextPreview.blobUrl || null,
      groupId: nextPreview.groupId || initialGroupId || null,
      projectId: nextPreview.projectId || currentProject?.id || null,
      status: nextPreview.status || "draft",
      selectionKey: selectedHistoryDoc?.id ?? historySelectionKey ?? null,
      generationTime: nextPreview.generationTime || null,
    });
  }, [docType, instructions, currentProject?.id, initialGroupId, selectedHistoryDoc?.id, historySelectionKey]);

  function handlePreviewStateChange(updatedPreview) {
    setPreview(updatedPreview);
    persistPreviewState(updatedPreview);
  }

  useEffect(() => {
    async function loadSelectedHistoryDoc() {
      if (!selectedHistoryDoc) return;
      if (shouldRestoreState && preview?.documentId === selectedHistoryDoc.id) return;
      setSelectedDocLoading(true);
      setSelectedDocError(null);
      try {
        const doc = await getDocument(selectedHistoryDoc.id, authHeaders);
        const previewState = {
          mode: "view",
          markdown: doc.markdown_content || "",
          changedSections: [],
          docType: doc.doc_type,
          documentId: doc.id,
          version: doc.version,
          filename: `${doc.doc_type}_${doc.version}.docx`,
          blobUrl: null,
          groupId: doc.document_group_id,
          projectId: doc.project_id,
          instructions: doc.instructions,
          status: doc.status,
        };
        setDocType(doc.doc_type);
        setInstructions(doc.instructions || "");
        setPreview(previewState);
        persistPreviewState(previewState);
      } catch (err) {
        setSelectedDocError(err.message || "Failed to load history document.");
      } finally {
        setSelectedDocLoading(false);
      }
    }

    loadSelectedHistoryDoc();
  }, [selectedHistoryDoc, authHeaders, shouldRestoreState, preview?.documentId, persistPreviewState]);

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
    clearPreviewState();
    setDocType(initialDocType || "BRD");
    setInstructions(initialInstructions || "");
    setFile(null);
    setShowFileUpload(false);
    setError(null);
    setPreview(null);
    setSelectedDocError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onClearHistorySelection?.();
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
      const { markdown, changed_sections, generation_time_seconds } = await previewDoc(formData, authHeaders);
      
      const previewState = {
        mode: "draft",
        docType,
        instructions,
        markdown,
        changedSections: changed_sections,
        generationTime: generation_time_seconds,
        documentId: null,
        version: null,
        filename: null,
        blobUrl: null,
        groupId: initialGroupId || null,
        projectId: currentProject?.id || null,
        status: "draft",
      };
      setPreview(previewState);
      persistPreviewState(previewState);
      addToast("Preview ready — review and confirm to download", "info");
    } catch (err) {
      setError(err.message || "Generation failed. Is Ollama running?");
    } finally {
      setLoading(false);
    }
  }

  if (loading || (selectedHistoryDoc && !preview && selectedDocLoading)) {
    return (
      <div className="card">
        <div className="card-title">Generate Document</div>
        <LoadingSpinner />
      </div>
    );
  }

  if (selectedDocError) {
    return (
      <div className="card">
        <div className="card-title">Generate Document</div>
        <div className="error-message">{selectedDocError}</div>
        <button className="btn btn-secondary" type="button" onClick={handleReset}>
          Back to generator
        </button>
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
          preview={preview}
          groupId={initialGroupId || null}
          projectId={currentProject?.id || null}
          onReset={handleReset}
          onGenerated={onGenerated}
          addToast={addToast}
          onPreviewChange={handlePreviewStateChange}
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
