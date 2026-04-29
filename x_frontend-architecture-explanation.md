# Frontend Architecture Summary — DocGen

## 1. Routing & Structure

### Entry point
- `frontend/src/main.jsx` mounts the React app into the DOM using `createRoot`.
- It wraps `App` with `AuthProvider` from `frontend/src/contexts/AuthContext.jsx`.
- No additional global state library is used (React context only).

### App structure
- `frontend/src/App.jsx` is the root component.
- It uses `BrowserRouter` from React Router v6 to enable client-side routing.
- `App` renders `AuthGate`, which conditionally renders either `LoginPage` or `AppShell`.
- `AppShell` contains the authenticated application layout, header, and `<Routes>`.

### React Router wiring
- `<BrowserRouter>` is the top-level router provider.
- `<Routes>` defines route paths:
  - `/` → main generate page combining `DocForm` and `DocHistory`
  - `/analytics` → `AnalyticsDashboard` (visible only for approver/admin users)
  - `/admin` → `AdminPanel` (visible only for admin users)
  - `/projects/:projectId/settings` → `ProjectSettings`
  - `*` → `RedirectHome`, which uses `useNavigate` to redirect unauthorized or invalid routes back to `/`
- Navigation links are built using `<NavLink>`.
- Route access is gated by `AuthContext` role flags `isAdmin` and `isApprover`.

## 2. State Management

### AuthContext implementation
- File: `frontend/src/contexts/AuthContext.jsx`
- Uses React context and state hooks only.
- Stores user authentication state and current project selection.
- Persists data in `localStorage`:
  - `docgen_token` stores the JWT access token.
  - `docgen_project` stores selected project metadata.
- On load, `loadFromStorage()` decodes the JWT payload and checks expiration.
- The decoded user object is shaped as:
  - `{ id: claims.sub, name: claims.name, email: claims.email, role: claims.role }`
- Exposes `login`, `logout`, `setCurrentProject`, and `authHeaders` helper.
- `authHeaders()` returns `{ Authorization: `Bearer ${token}` }` when a valid token exists.

### Global state exposed
- `user`: authenticated user profile
- `token`: JWT string
- `currentProject`: selected project object
- `authHeaders`: callback to attach auth headers to API requests
- `isAdmin`: boolean if user role is `admin`
- `isApprover`: boolean if user role is `approver` or `admin`

### Other local state patterns
- `AppShell` uses component-local state for toast messages, refresh triggers, and bulk modal visibility.
- `DocForm` uses local `useState` for form inputs, file upload state, preview state, and loading/error state.
- `PreviewPanel` uses local state for phase progression, markdown editing, and download metadata.
- `DocHistory` uses local state for filters, search, current document list, and versioning flows.

## 3. API Integration

### Service layer
- File: `frontend/src/services/api.js`
- Implements raw `fetch` wrappers for all backend endpoints.
- No Axios usage; `fetch` is used consistently.
- No built-in interceptors: authorization header injection is handled manually by passing `getHeaders` callbacks from components.

### Common response handling
- `handleResponse` checks `response.ok`.
- On failure, it tries to parse JSON and throws a generic `Error` with the backend `detail`.
- Successful responses are returned as JSON or blobs depending on the endpoint.

### Key endpoint payloads
- `previewDoc(formData, getHeaders)`
  - POST `/preview-doc`
  - Body: `FormData`
  - Form keys: `doc_type`, `instructions`, `project_id`, `previous_file`
  - Response: `{ markdown, changed_sections }`
- `buildDoc(formData, getHeaders)`
  - POST `/build-doc`
  - Body: `FormData`
  - Form keys: `doc_type`, `instructions`, `markdown`, `group_id`, `project_id`
  - Response: blob `.docx`; headers include `Content-Disposition`, `X-Document-Id`, `X-Group-Id`, `X-Version`
- `generateDoc(formData, getHeaders)`
  - POST `/generate-doc`
  - Similar to `buildDoc`, returns blob and document metadata
- `regenerateSection(payload, getHeaders)`
  - POST `/regenerate-section`
  - JSON payload: `{ document_id, section_name, new_instructions }`
- `generateBulk(payload, getHeaders)`
  - POST `/generate-bulk`
  - JSON payload includes bulk generation request structure

### Auth and project headers
- Components call `authHeaders()` from `useAuth()` and pass it to API functions.
- Example pattern: `await previewDoc(formData, authHeaders)`
- `authHeaders()` may return `{ Authorization: `Bearer ${token}` }` when a token is available.

## 4. Key Components

### `frontend/src/components/DocForm.jsx`
- Responsible for the document generation form and preview trigger.
- Tracks:
  - `docType`
  - `instructions`
  - uploaded `file`
  - `preview` response state
  - `loading` and `error`
- Handles multipart/form-data upload using `FormData`.
- Accepts `.docx` and `.pdf` uploads for `previous_file`.
- Submits preview requests via `previewDoc(formData, authHeaders)`.
- On success, stores preview payload and transitions to `PreviewPanel`.
- Also renders `SnippetsPanel` to append reusable instruction snippets.
- Ctrl+Enter keyboard shortcut is wired in `useEffect` for fast submission.

### `frontend/src/components/PreviewPanel.jsx`
- Handles the markdown preview workflow and final build/download stage.
- Receives preview markdown and changed section metadata from `DocForm`.
- Supports:
  - rendered markdown preview
  - inline markdown editing mode
  - confirm-and-download via `buildDoc` POST
  - document status updates
  - section regeneration via `regenerateSection`
  - AI review and compliance score flows
- The download flow:
  - `handleConfirm()` builds a `FormData` payload containing `doc_type`, `instructions`, `markdown`, and optional `group_id` / `project_id`
  - Calls `buildDoc(fd, authHeaders)`
  - Receives a blob and filename, then triggers a browser download using `URL.createObjectURL`
- Has a lightweight custom markdown renderer to convert headings, lists, tables, and bold text into React elements.
- Changes to the markdown are editable in-place with a toggle between rendered preview and raw markdown textarea.

### `frontend/src/components/DocHistory.jsx`
- Fetches document history from the backend via `getDocuments(filters, authHeaders)`.
- Includes UI for searching, filtering by `doc_type` and `status`, and project-scoped history.
- Supports starting a new version from an existing document by rendering a `DocForm` with `initialDocType`, `initialInstructions`, and `initialGroupId`.
- Uses `updateStatus(doc.id, nextStatus, authHeaders)` to manage workflow transitions.
- The history panel is a secondary column on the main page, not a separate route.

## 5. Styling

### `frontend/src/styles/theme.css`
- Uses CSS custom properties for primary design tokens:
  - `--primary`, `--secondary`, `--accent`, `--bg`, `--surface`, `--border`, `--error`, `--success`, `--warning`
  - shadows, border radius, and font stack.
- Layout is grid-based:
  - `.app-body` uses `grid-template-columns: 480px 1fr` on desktop.
  - Responsive fallback collapses to a single column under `900px`.
- Cards are styled with soft surfaces, borders, and shadow.
- Form controls are standard CSS with focus outlines, border transitions, and full width.
- File upload area is a dashed drag/drop-like panel styled with hover state.
- Buttons are class-based (`.btn`, `.btn-primary`, `.btn-secondary`, `.btn-download`) with consistent spacing and hover effects.
- History list and preview panels use utility classes for badges, status pills, and scroll containers.

## 6. Important design notes

- The frontend intentionally avoids heavy third-party state libraries and uses React Router v6 + React context only.
- API auth is manually attached at call time through `getHeaders` rather than an interceptor architecture.
- Document generation is a two-step flow:
  1. `DocForm` sends preview request to `/preview-doc`
  2. `PreviewPanel` confirms and sends build request to `/build-doc`
- File uploads are only used for `previous_file` in preview generation; the actual download stream is handled by `fetch` returning a blob.
- The preview flow is optimized for an intermediate review step, not immediate direct download.

## 7. Exact files to inspect for deeper debugging

- `frontend/src/services/api.js`
- `frontend/src/components/DocForm.jsx`
- `frontend/src/components/PreviewPanel.jsx`
- `frontend/src/contexts/AuthContext.jsx`
- `frontend/src/App.jsx`
- `frontend/src/main.jsx`
- `frontend/src/styles/theme.css`
