const BASE_URL = "http://localhost:8000";

async function handleResponse(response) {
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Server error: ${response.status}`);
  }
  return response;
}

// ── Generation ─────────────────────────────────────────────────────────────────

export async function previewDoc(formData, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/preview-doc`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    })
  );
  return res.json(); // { markdown, changed_sections }
}

export async function buildDoc(formData, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/build-doc`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    })
  );
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const filename = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "document.docx";
  return {
    blob,
    filename,
    docId: res.headers.get("X-Document-Id"),
    groupId: res.headers.get("X-Group-Id"),
    version: res.headers.get("X-Version"),
  };
}

export async function generateDoc(formData, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/generate-doc`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    })
  );
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const filename = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "document.docx";
  return { blob, filename, docId: res.headers.get("X-Document-Id") };
}

export async function regenerateSection(payload, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/regenerate-section`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(payload),
    })
  );
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const filename = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "document.docx";
  return { blob, filename };
}

export async function generateBulk(payload, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/generate-bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(payload),
    })
  );
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const filename = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "documents.zip";
  return { blob, filename };
}

// ── Documents ──────────────────────────────────────────────────────────────────

export async function getDocuments(filters = {}, getHeaders = () => ({})) {
  const params = new URLSearchParams();
  if (filters.doc_type) params.set("doc_type", filters.doc_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);
  if (filters.project_id) params.set("project_id", filters.project_id);
  const qs = params.toString();
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents${qs ? "?" + qs : ""}`, { headers: getHeaders() })
  );
  return res.json();
}

export async function getDocumentDiff(docId, prevDocId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/diff/${prevDocId}`, { headers: getHeaders() })
  );
  return res.json();
}

export async function getDocument(docId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}`, { headers: getHeaders() })
  );
  return res.json();
}

export async function updateStatus(docId, status, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ status }),
    })
  );
  return res.json();
}

export async function getDocumentGroup(groupId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/group/${groupId}`, { headers: getHeaders() })
  );
  return res.json();
}

// ── Comments ───────────────────────────────────────────────────────────────────

export async function getComments(docId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/comments`, { headers: getHeaders() })
  );
  return res.json();
}

export async function addComment(docId, comment, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(comment),
    })
  );
  return res.json();
}

export async function resolveComment(commentId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/comments/${commentId}/resolve`, {
      method: "PATCH",
      headers: getHeaders(),
    })
  );
  return res.json();
}

// ── Snippets ───────────────────────────────────────────────────────────────────

export async function getSnippets(docType, getHeaders = () => ({})) {
  const qs = docType ? `?doc_type=${encodeURIComponent(docType)}` : "";
  const res = await handleResponse(
    await fetch(`${BASE_URL}/snippets${qs}`, { headers: getHeaders() })
  );
  return res.json();
}

export async function getPopularSnippets(getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/snippets/popular`, { headers: getHeaders() })
  );
  return res.json();
}

export async function createSnippet(snippet, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/snippets`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(snippet),
    })
  );
  return res.json();
}

export async function useSnippet(snippetId, getHeaders = () => ({})) {
  await fetch(`${BASE_URL}/snippets/${snippetId}/use`, {
    method: "PATCH",
    headers: getHeaders(),
  });
}

export async function deleteSnippet(snippetId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/snippets/${snippetId}`, {
      method: "DELETE",
      headers: getHeaders(),
    })
  );
  return res.json();
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export async function login(email, password) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
  );
  return res.json(); // { access_token, token_type }
}

export async function register(name, email, password) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    })
  );
  return res.json();
}

export async function getMe(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/auth/me`, { headers: getHeaders() })
  );
  return res.json();
}

// ── Notifications ──────────────────────────────────────────────────────────────

export async function getNotifications(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/notifications`, { headers: getHeaders() })
  );
  return res.json();
}

export async function getUnreadCount(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/notifications/unread-count`, { headers: getHeaders() })
  );
  return res.json(); // { count }
}

export async function markRead(notifId, getHeaders) {
  await fetch(`${BASE_URL}/notifications/${notifId}/read`, {
    method: "PATCH",
    headers: getHeaders(),
  });
}

export async function markAllRead(getHeaders) {
  await fetch(`${BASE_URL}/notifications/read-all`, {
    method: "PATCH",
    headers: getHeaders(),
  });
}

// ── Admin ──────────────────────────────────────────────────────────────────────

export async function listTemplates(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/templates`, { headers: getHeaders() })
  );
  return res.json();
}

export async function getTemplate(name, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/templates/${encodeURIComponent(name)}`, {
      headers: getHeaders(),
    })
  );
  return res.json();
}

export async function updateTemplate(name, content, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/templates/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ content }),
    })
  );
  return res.json();
}

export async function getBrandGuide(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/brand-guide`, { headers: getHeaders() })
  );
  return res.json();
}

export async function updateBrandGuide(content, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/brand-guide`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ content }),
    })
  );
  return res.json();
}

export async function getSystemPrompt(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/system-prompt`, { headers: getHeaders() })
  );
  return res.json();
}

export async function updateSystemPrompt(content, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/system-prompt`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ content }),
    })
  );
  return res.json();
}

export async function getModelConfig(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/config/model`, { headers: getHeaders() })
  );
  return res.json();
}

export async function setModelConfig(model, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/config/model`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ model }),
    })
  );
  return res.json();
}

export async function listUsers(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/users`, { headers: getHeaders() })
  );
  return res.json();
}

export async function deleteUser(userId, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/admin/users/${userId}`, {
      method: "DELETE",
      headers: getHeaders(),
    })
  );
  return res.json();
}

// ── Projects ───────────────────────────────────────────────────────────────────

export async function getProjects(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects`, { headers: getHeaders() })
  );
  return res.json();
}

export async function createProject(payload, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(payload),
    })
  );
  return res.json();
}

export async function getProject(projectId, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}`, { headers: getHeaders() })
  );
  return res.json();
}

export async function updateProject(projectId, payload, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(payload),
    })
  );
  return res.json();
}

export async function getProjectMembers(projectId, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/members`, { headers: getHeaders() })
  );
  return res.json();
}

export async function addProjectMember(projectId, payload, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify(payload),
    })
  );
  return res.json();
}

export async function removeProjectMember(projectId, userId, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/members/${userId}`, {
      method: "DELETE",
      headers: getHeaders(),
    })
  );
  return res.json();
}

export async function uploadProjectLogo(projectId, type, file, getHeaders) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/logo/${type}`, {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    })
  );
  return res.json();
}

export async function uploadProjectImage(projectId, file, getHeaders) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/images`, {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    })
  );
  return res.json();
}

export async function getProjectImages(projectId, getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/projects/${projectId}/images`, { headers: getHeaders() })
  );
  return res.json();
}

// ── Analytics ──────────────────────────────────────────────────────────────────

export async function getAnalytics(getHeaders) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/analytics/data`, { headers: getHeaders() })
  );
  return res.json();
}

// ── AI Review ──────────────────────────────────────────────────────────────────

export async function runAIReview(docId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/ai-review`, {
      method: "POST",
      headers: getHeaders(),
    })
  );
  return res.json(); // { doc_id, issues, comments_created }
}

// ── Compliance Scoring ─────────────────────────────────────────────────────────

export async function getComplianceRubrics(getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/compliance-rubrics`, { headers: getHeaders() })
  );
  return res.json(); // { rubrics: [...] }
}

export async function getComplianceScores(docId, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/compliance-scores`, { headers: getHeaders() })
  );
  return res.json(); // array of score objects
}

export async function runComplianceScore(docId, rubricName, getHeaders = () => ({})) {
  const res = await handleResponse(
    await fetch(`${BASE_URL}/documents/${docId}/compliance-score`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getHeaders() },
      body: JSON.stringify({ rubric_name: rubricName }),
    })
  );
  return res.json(); // { id, doc_id, rubric, score, criteria, scored_at }
}
