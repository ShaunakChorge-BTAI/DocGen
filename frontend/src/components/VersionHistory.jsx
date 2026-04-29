import { useState, useEffect } from "react";
import { getDocumentGroup } from "../services/api";

// Minimal Myers-style line diff — returns array of { type: "same"|"added"|"removed", text }
function lineDiff(oldText, newText) {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const m = a.length;
  const n = b.length;

  // Build LCS (longest common subsequence) table
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to build diff
  const result = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.unshift({ type: "same", text: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: "added", text: b[j - 1] });
      j--;
    } else {
      result.unshift({ type: "removed", text: a[i - 1] });
      i--;
    }
  }
  return result;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function VersionHistory({ groupId, onClose }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedA, setSelectedA] = useState(null); // older
  const [selectedB, setSelectedB] = useState(null); // newer
  const [diff, setDiff] = useState(null);

  useEffect(() => {
    setLoading(true);
    getDocumentGroup(groupId)
      .then((docs) => {
        setVersions(docs);
        if (docs.length >= 2) {
          setSelectedA(docs[docs.length - 2]);
          setSelectedB(docs[docs.length - 1]);
        } else if (docs.length === 1) {
          setSelectedB(docs[0]);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [groupId]);

  useEffect(() => {
    if (selectedA && selectedB && selectedA.markdown_content && selectedB.markdown_content) {
      setDiff(lineDiff(selectedA.markdown_content, selectedB.markdown_content));
    } else {
      setDiff(null);
    }
  }, [selectedA, selectedB]);

  function statusColor(s) {
    return { draft: "#6b7280", in_review: "#d97706", approved: "#16a34a", rejected: "#dc2626" }[s] || "#6b7280";
  }

  return (
    <div className="version-history-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="version-history-modal">
        <div className="vh-header">
          <span className="vh-title">Version History</span>
          <button className="vh-close" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div className="vh-loading">Loading versions…</div>
        ) : (
          <>
            <div className="vh-version-list">
              {versions.map((v) => (
                <div
                  key={v.id}
                  className={`vh-version-item ${
                    selectedA?.id === v.id ? "vh-selected-a" : selectedB?.id === v.id ? "vh-selected-b" : ""
                  }`}
                >
                  <div className="vh-version-info">
                    <strong>{v.version}</strong>
                    <span style={{ color: statusColor(v.status), fontSize: 11 }}> · {v.status}</span>
                    <div className="vh-version-date">{formatDate(v.created_at)}</div>
                  </div>
                  <div className="vh-version-actions">
                    {v.markdown_content && (
                      <>
                        <button
                          className={`vh-select-btn ${selectedA?.id === v.id ? "active" : ""}`}
                          onClick={() => setSelectedA(v)}
                        >
                          Base
                        </button>
                        <button
                          className={`vh-select-btn ${selectedB?.id === v.id ? "active" : ""}`}
                          onClick={() => setSelectedB(v)}
                        >
                          Compare
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {diff ? (
              <div className="vh-diff">
                <div className="vh-diff-legend">
                  <span className="diff-added-label">+ Added</span>
                  <span className="diff-removed-label">- Removed</span>
                  <span className="diff-same-label">  Unchanged</span>
                </div>
                <div className="vh-diff-body">
                  {diff.map((line, i) => (
                    <div
                      key={i}
                      className={`diff-line diff-${line.type}`}
                    >
                      <span className="diff-prefix">
                        {line.type === "added" ? "+" : line.type === "removed" ? "-" : " "}
                      </span>
                      <span className="diff-text">{line.text || "\u00A0"}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : selectedB && !selectedA ? (
              <div className="vh-diff">
                <div className="vh-diff-body">
                  <pre className="vh-single-version">{selectedB.markdown_content || "(no content)"}</pre>
                </div>
              </div>
            ) : (
              <div className="vh-no-diff">
                Select two versions above to compare them.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
