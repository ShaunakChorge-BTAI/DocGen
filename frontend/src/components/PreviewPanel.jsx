import { useState, useEffect } from "react";
import { buildDoc, regenerateSection, updateStatus, runAIReview, getComplianceRubrics, runComplianceScore, getComplianceScores } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import CommentPanel from "./CommentPanel";

const STATUS_COLORS = {
  draft: "#6b7280",
  in_review: "#d97706",
  approved: "#16a34a",
  rejected: "#dc2626",
};

const STATUS_TRANSITIONS = {
  draft: [{ label: "Send for Review", next: "in_review" }],
  in_review: [
    { label: "Approve", next: "approved" },
    { label: "Reject", next: "rejected" },
  ],
  rejected: [{ label: "Reset to Draft", next: "draft" }],
  approved: [],
};

// Parse **bold** text into React elements — no raw HTML
function parseBold(text) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? <strong key={i}>{part}</strong> : part
  );
}

// Lightweight markdown → React element renderer
function renderMarkdown(markdown, onRegenerate) {
  const lines = markdown.split("\n");
  const elements = [];
  let i = 0;
  let listItems = [];
  let listType = null;
  let keyCounter = 0;
  const nextKey = () => keyCounter++;

  function flushList() {
    if (!listItems.length) return;
    const Tag = listType === "ol" ? "ol" : "ul";
    elements.push(
      <Tag key={nextKey()} className="md-list">
        {listItems.map((item, idx) => (
          <li key={idx}>{parseBold(item)}</li>
        ))}
      </Tag>
    );
    listItems = [];
    listType = null;
  }

  while (i < lines.length) {
    const line = lines[i];

    // Headings
    const hMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (hMatch) {
      flushList();
      const level = hMatch[1].length;
      const title = hMatch[2];
      const Tag = `h${level}`;
      const isSection = level <= 2;
      elements.push(
        <div key={nextKey()} className={`md-heading-row${isSection ? " md-section-heading" : ""}`}>
          <Tag className={`md-h${level}`}>{parseBold(title)}</Tag>
          {isSection && onRegenerate && (
            <button
              type="button"
              className="regen-btn"
              onClick={() => onRegenerate(title)}
              title={`Regenerate: ${title}`}
            >
              ⟳ Regenerate
            </button>
          )}
        </div>
      );
      i++;
      continue;
    }

    // Table rows
    if (line.startsWith("|")) {
      flushList();
      const tableLines = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const rows = tableLines
        .filter((l) => !/^\|[-| :]+\|$/.test(l.trim()))
        .map((r) => r.split("|").slice(1, -1).map((c) => c.trim()));
      if (rows.length) {
        elements.push(
          <table key={nextKey()} className="md-table">
            <thead>
              <tr>{(rows[0] || []).map((cell, ci) => <th key={ci}>{cell}</th>)}</tr>
            </thead>
            <tbody>
              {rows.slice(1).map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => <td key={ci}>{parseBold(cell)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        );
      }
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^[-*]\s+(.*)/);
    if (ulMatch) {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listItems.push(ulMatch[1]);
      i++;
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^\d+\.\s+(.*)/);
    if (olMatch) {
      if (listType !== "ol") { flushList(); listType = "ol"; }
      listItems.push(olMatch[1]);
      i++;
      continue;
    }

    flushList();

    if (!line.trim()) { i++; continue; }

    elements.push(<p key={nextKey()} className="md-p">{parseBold(line)}</p>);
    i++;
  }

  flushList();
  return elements;
}

// ── RegenModal ─────────────────────────────────────────────────────────────────
function RegenModal({ sectionName, onConfirm, onCancel }) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!instructions.trim()) return;
    setBusy(true);
    await onConfirm(sectionName, instructions.trim());
    setBusy(false);
  }

  return (
    <div className="regen-modal-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="regen-modal">
        <div className="regen-modal-title">Regenerate: {sectionName}</div>
        <form onSubmit={submit}>
          <textarea
            autoFocus
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="What should change in this section?"
            rows={4}
            className="regen-modal-textarea"
          />
          <div className="regen-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={busy || !instructions.trim()}>
              {busy ? "Regenerating…" : "Regenerate"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── ConfirmDialog ──────────────────────────────────────────────────────────────
function ConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div className="regen-modal-overlay" onClick={onCancel}>
      <div className="regen-modal" onClick={(e) => e.stopPropagation()}>
        <div className="regen-modal-title">{message}</div>
        <div className="regen-modal-actions">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

// ── Main PreviewPanel ──────────────────────────────────────────────────────────
export default function PreviewPanel({
  docType,
  instructions,
  markdown: initialMarkdown,
  changedSections,
  groupId,
  projectId,
  onReset,
  onGenerated,
  addToast,
}) {
  const { authHeaders } = useAuth();
  const [phase, setPhase] = useState("previewing"); // previewing | building | built
  const [editMode, setEditMode] = useState(false);
  const [markdown, setMarkdown] = useState(initialMarkdown);
  const [docId, setDocId] = useState(null);
  const [builtGroupId, setBuiltGroupId] = useState(groupId || null);
  const [blob, setBlob] = useState(null);
  const [filename, setFilename] = useState(null);
  const [version, setVersion] = useState(null);
  const [activeTab, setActiveTab] = useState("document");
  const [docStatus, setDocStatus] = useState("draft");
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [regenSection, setRegenSection] = useState(null);

  // AI Review state
  const [aiReviewRunning, setAiReviewRunning] = useState(false);
  const [aiReviewResult, setAiReviewResult] = useState(null);

  // Compliance state
  const [rubrics, setRubrics] = useState([]);
  const [selectedRubric, setSelectedRubric] = useState("");
  const [complianceRunning, setComplianceRunning] = useState(false);
  const [complianceScores, setComplianceScores] = useState([]);

  useEffect(() => {
    getComplianceRubrics(authHeaders).then((d) => {
      setRubrics(d.rubrics || []);
      if (d.rubrics?.length) setSelectedRubric(d.rubrics[0]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (docId) {
      getComplianceScores(docId, authHeaders).then(setComplianceScores).catch(() => {});
    }
  }, [docId]);

  async function handleAIReview() {
    setAiReviewRunning(true);
    try {
      const result = await runAIReview(docId, authHeaders);
      setAiReviewResult(result);
      addToast(`AI review complete — ${result.comments_created} comment(s) added`, "success");
    } catch (err) {
      addToast(err.message || "AI review failed", "error");
    } finally {
      setAiReviewRunning(false);
    }
  }

  async function handleComplianceScore() {
    if (!selectedRubric) return;
    setComplianceRunning(true);
    try {
      const result = await runComplianceScore(docId, selectedRubric, authHeaders);
      setComplianceScores((prev) => [result, ...prev]);
      addToast(`Compliance score: ${result.score}/100`, result.score >= 80 ? "success" : result.score >= 60 ? "info" : "error");
    } catch (err) {
      addToast(err.message || "Scoring failed", "error");
    } finally {
      setComplianceRunning(false);
    }
  }

  function triggerDownload(b, name) {
    const url = URL.createObjectURL(b);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function handleConfirm() {
    setPhase("building");
    const fd = new FormData();
    fd.append("doc_type", docType);
    fd.append("instructions", instructions);
    fd.append("markdown", markdown);
    if (builtGroupId) fd.append("group_id", builtGroupId);
    if (projectId) fd.append("project_id", projectId);

    try {
      const result = await buildDoc(fd, authHeaders);
      setBlob(result.blob);
      setFilename(result.filename);
      setDocId(result.docId);
      setBuiltGroupId(result.groupId || builtGroupId);
      setVersion(result.version);
      setPhase("built");
      triggerDownload(result.blob, result.filename);
      onGenerated();
      addToast("Document built and downloaded", "success");
    } catch (err) {
      setPhase("previewing");
      addToast(err.message || "Build failed", "error");
    }
  }

  async function handleStatusChange(next) {
    try {
      await updateStatus(docId, next, authHeaders);
      setDocStatus(next);
      setConfirmDialog(null);
      addToast(`Status → ${next.replace("_", " ")}`, "success");
    } catch {
      addToast("Failed to update status", "error");
    }
  }

  async function handleRegenSection(sectionName, newInstructions) {
    try {
      const result = await regenerateSection({
        document_id: Number(docId),
        section_name: sectionName,
        new_instructions: newInstructions,
      });
      setBlob(result.blob);
      setFilename(result.filename);
      triggerDownload(result.blob, result.filename);
      setRegenSection(null);
      addToast(`"${sectionName}" regenerated and downloaded`, "success");
    } catch (err) {
      addToast(err.message || "Regeneration failed", "error");
    }
  }

  function ChangedBanner() {
    if (!changedSections?.length) return null;
    const isAll = changedSections[0]?.toLowerCase() === "all sections";
    return (
      <div className={`changed-banner${isAll ? " changed-banner-all" : ""}`}>
        {isAll
          ? "New document — all sections generated"
          : <><strong>Changed sections:</strong> {changedSections.join(", ")}</>}
      </div>
    );
  }

  const transitions = STATUS_TRANSITIONS[docStatus] || [];

  // ── Building spinner ─────────────────────────────────────────────────────────
  if (phase === "building") {
    return (
      <div className="preview-card">
        <div className="spinner-overlay">
          <div className="spinner" />
          <div className="spinner-text">Building branded .docx…</div>
        </div>
      </div>
    );
  }

  // ── Preview (pre-build) ──────────────────────────────────────────────────────
  if (phase === "previewing") {
    return (
      <div className="preview-card">
        <div className="preview-card-header">
          <span className="preview-card-title">Preview — {docType}</span>
          <button
            type="button"
            className={`toggle-btn${editMode ? " active" : ""}`}
            onClick={() => setEditMode((e) => !e)}
          >
            {editMode ? "View rendered" : "Edit markdown"}
          </button>
        </div>

        <ChangedBanner />

        <div className="md-preview-area">
          {editMode ? (
            <textarea
              className="md-edit-textarea"
              value={markdown}
              onChange={(e) => setMarkdown(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <div className="md-rendered">{renderMarkdown(markdown, null)}</div>
          )}
        </div>

        <div className="preview-actions-row">
          <button type="button" className="btn btn-secondary" onClick={onReset}>
            ← Back
          </button>
          <button type="button" className="btn btn-download" onClick={handleConfirm}>
            Confirm &amp; Download
          </button>
        </div>
      </div>
    );
  }

  // ── Built (post-download) ────────────────────────────────────────────────────
  return (
    <>
      {regenSection && (
        <RegenModal
          sectionName={regenSection}
          onConfirm={handleRegenSection}
          onCancel={() => setRegenSection(null)}
        />
      )}
      {confirmDialog && (
        <ConfirmDialog
          message={`Change status to "${confirmDialog.next.replace("_", " ")}"?`}
          onConfirm={() => handleStatusChange(confirmDialog.next)}
          onCancel={() => setConfirmDialog(null)}
        />
      )}

      <div className="preview-card">
        <div className="preview-card-header">
          <span className="preview-card-title">{docType} · {version}</span>
          <span className="status-badge" style={{ background: STATUS_COLORS[docStatus] }}>
            {docStatus.replace("_", " ")}
          </span>
        </div>

        <div className="preview-built-actions">
          <button className="btn btn-download" onClick={() => triggerDownload(blob, filename)}>
            ⬇ Download again
          </button>
          <button className="btn btn-secondary" onClick={onReset}>
            Generate another
          </button>
        </div>

        <div className="preview-tabs">
          {[
            { id: "document", label: "Document" },
            { id: "comments", label: "Comments" },
            { id: "ai-review", label: "AI Review" },
            { id: "compliance", label: "Compliance" },
            { id: "status", label: "Status" },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`preview-tab${activeTab === tab.id ? " active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "document" && (
          <div className="md-preview-area">
            <div className="md-rendered">
              {renderMarkdown(markdown, (name) => setRegenSection(name))}
            </div>
          </div>
        )}

        {activeTab === "comments" && (
          <CommentPanel docId={docId} addToast={addToast} />
        )}

        {activeTab === "ai-review" && (
          <div className="ai-review-panel">
            <div className="ai-review-header">
              <p className="ai-review-desc">
                Run a second LLM pass to detect completeness gaps, contradictions, missing requirements,
                and structural issues. Results are saved as comments on this document.
              </p>
              <button
                className="btn btn-primary"
                onClick={handleAIReview}
                disabled={aiReviewRunning}
              >
                {aiReviewRunning ? "Reviewing…" : "Run AI Review"}
              </button>
            </div>

            {aiReviewResult && (
              <div className="ai-review-results">
                {aiReviewResult.issues.length === 0 ? (
                  <div className="ai-review-clean">No issues found — document looks good.</div>
                ) : (
                  <>
                    <div className="ai-review-summary">
                      {aiReviewResult.issues.length} issue(s) found · {aiReviewResult.comments_created} comment(s) added
                    </div>
                    {aiReviewResult.issues.map((issue, i) => (
                      <div key={i} className={`ai-issue ai-issue-${issue.issue_type}`}>
                        <div className="ai-issue-header">
                          <span className="ai-issue-type">{issue.issue_type.replace(/_/g, " ")}</span>
                          <span className="ai-issue-section">{issue.section}</span>
                        </div>
                        <div className="ai-issue-desc">{issue.description}</div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "compliance" && (
          <div className="compliance-panel">
            <div className="compliance-controls">
              <select
                className="compliance-rubric-select"
                value={selectedRubric}
                onChange={(e) => setSelectedRubric(e.target.value)}
                disabled={complianceRunning}
              >
                {rubrics.length === 0 && <option value="">No rubrics found</option>}
                {rubrics.map((r) => (
                  <option key={r} value={r}>{r.replace(/-/g, " ")}</option>
                ))}
              </select>
              <button
                className="btn btn-primary"
                onClick={handleComplianceScore}
                disabled={complianceRunning || !selectedRubric}
              >
                {complianceRunning ? "Scoring…" : "Score Document"}
              </button>
            </div>

            {complianceScores.length > 0 && (() => {
              const latest = complianceScores[0];
              const color = latest.score >= 80 ? "#16a34a" : latest.score >= 60 ? "#d97706" : "#dc2626";
              return (
                <div className="compliance-result">
                  <div className="compliance-score-header">
                    <span className="compliance-rubric-label">{latest.rubric.replace(/-/g, " ")}</span>
                    <span className="compliance-score-number" style={{ color }}>{latest.score}<span className="compliance-score-max">/100</span></span>
                  </div>
                  <div className="compliance-bar-track">
                    <div className="compliance-bar-fill" style={{ width: `${latest.score}%`, background: color }} />
                  </div>
                  <div className="compliance-criteria-list">
                    {latest.criteria.map((c, i) => (
                      <div key={i} className={`compliance-criterion compliance-criterion-${c.status}`}>
                        <span className="compliance-criterion-status">{c.status === "pass" ? "✓" : "✗"}</span>
                        <span className="compliance-criterion-name">{c.criterion}</span>
                        {c.note && <span className="compliance-criterion-note">{c.note}</span>}
                      </div>
                    ))}
                  </div>
                  {complianceScores.length > 1 && (
                    <details className="compliance-history">
                      <summary>{complianceScores.length - 1} previous score(s)</summary>
                      {complianceScores.slice(1).map((s, i) => (
                        <div key={i} className="compliance-history-item">
                          {s.rubric.replace(/-/g, " ")} — {s.score}/100 · {new Date(s.scored_at).toLocaleString()}
                        </div>
                      ))}
                    </details>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {activeTab === "status" && (
          <div className="status-panel">
            <div className="status-current">
              Current status:{" "}
              <span style={{ color: STATUS_COLORS[docStatus], fontWeight: 600 }}>
                {docStatus.replace("_", " ")}
              </span>
            </div>
            <div className="status-actions">
              {transitions.map((t) => (
                <button
                  key={t.next}
                  className="btn btn-secondary"
                  onClick={() => setConfirmDialog(t)}
                >
                  {t.label}
                </button>
              ))}
              {transitions.length === 0 && (
                <p className="status-final">
                  Document is <strong>{docStatus}</strong>. No further transitions.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
