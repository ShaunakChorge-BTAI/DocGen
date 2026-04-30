# DocGen — AI-Powered Document Generator: Complete Documentation

## 1. Project Overview
**DocGen** is a secure, internal web application designed for implementation teams to generate professional, brand-consistent business and technical documents (e.g., BRD, FSD, SRS, User Manuals, Product Brochures). 

The core value proposition of DocGen is data privacy and strict formatting: it operates using a **local LLM (Ollama)**, ensuring no proprietary or client data ever leaves the organization's network. It bridges the gap between raw AI generation and enterprise-ready deliverables by enforcing brand voice, tone, and formatting rules through customized templates and a dedicated `doc_builder` engine.

---

## 2. Project Flow (User Journey)
The DocGen user experience is built around a robust, two-step generation and collaboration workflow:

1. **Intake & Context:** The user selects a document type and optionally uploads a previous version of the document (.docx or .pdf). They provide plain-text instructions (or select saved snippets) describing what needs to be created or updated.
2. **Draft Preview (LLM Step):** The application sends the context to the local LLM. If a previous document is provided, it performs a diff-aware generation, changing only the requested sections. The frontend displays the result in a **Draft Mode** markdown preview.
3. **Review & Refine:** The user can edit the raw markdown inline or use the "Regenerate" button next to specific headings to prompt the LLM to rewrite individual sections without altering the rest of the document.
4. **Build & Persist (Confirm Step):** Once satisfied, the user clicks "Confirm." The system commits the document to the SQLite database, transitions the UI to **View Mode**, and securely generates the branded `.docx` or `.pdf` file in the backend.
5. **Download & Collaborate:** The user downloads the generated file. They can also add inline comments to sections, send the document through an approval workflow (Draft → In Review → Approved), or run AI compliance and review checks.
6. **Version Control:** If further updates are needed, users can view the document history and perform a side-by-side Myers LCS diff comparison between any two versions of the same document group.

---

## 3. Code Workflow (System Architecture)
The architecture follows a decoupled client-server model.

* **Client-Side (React/Vite):** * The user interacts with `DocForm.jsx`. Form data (including files via `FormData`) is sent to the backend via native `fetch` wrappers in `api.js`.
  * `AuthContext.jsx` manages session state via JWTs stored in `localStorage` and manually injects `Authorization` headers into API calls.
  * State is heavily managed via component-level React hooks and `sessionStorage` (to persist the draft preview across accidental page reloads).
* **Server-Side (FastAPI):**
  * Requests hit routers (e.g., `generate.py`).
  * `llm_service.py` constructs a master prompt combining the `system-prompt.md`, `brand-guide.md`, the specific document template, and user instructions. It streams this to the local Ollama instance via HTTP.
  * On confirmation, `doc_builder.py` intercepts the LLM's markdown output, parses the headings/tables/lists, and uses `python-docx` or `reportlab` to inject the content into a strictly branded binary file format.
  * The document metadata and markdown content are persisted to SQLite using SQLAlchemy ORM.

---

## 4. Libraries and Modules Used

### Backend (Python 3.11+)
* **FastAPI & Uvicorn:** Core web framework and ASGI server for high-performance API routing and handling concurrent LLM streaming.
* **SQLAlchemy:** The ORM used for all database interactions (`database.py`), mapping Python classes to SQLite tables.
* **python-docx:** Used in `doc_builder.py` to programmatically build Microsoft Word `.docx` files, apply specific brand colors, and format tables.
* **reportlab:** Used in `doc_builder.py` to generate branded PDF files as an alternative export format.
* **PyMuPDF (fitz):** Used in `file_parser.py` to extract raw text context from uploaded `.pdf` files for diff-aware regeneration.
* **python-jose & passlib (bcrypt):** Used in `auth_service.py` to generate, sign, and decode JWTs, and to hash user passwords.
* **httpx:** Used in `llm_service.py` to make asynchronous, streaming HTTP calls to the local Ollama API.
* **python-multipart:** Required by FastAPI to parse `FormData` streams for file uploads.

### Frontend (React 19 + Vite)
* **React Router v6 (`react-router-dom`):** Handles client-side routing (`App.jsx`), protecting routes based on roles (Admin, Approver).
* **Recharts:** Used in `AnalyticsDashboard.jsx` to render SVG-based charts (docs per day, status distributions).
* **Vite:** The build tool and development server, replacing standard Webpack for faster HMR (Hot Module Replacement).

---

## 5. Core Classes, Functions, and APIs

### Backend: Database Models (`models/database.py`)
* **`User`**: Stores credentials, emails, and roles (admin, author, reviewer, approver).
* **`Project` & `ProjectMember`**: Groups documents by client/initiative and enforces project-level access control.
* **`Document`**: The central entity. Stores `doc_type`, `instructions`, `markdown_content`, `version`, `status`, and `file_path`.
* **`Comment` & `Snippet`**: Stores inline document comments and reusable prompt fragments.
* **`ComplianceScore`**: Stores the results of AI-driven rubric checks.

### Backend: Key APIs (`routers/`)
* **`POST /preview-doc`**: (Step 1) Accepts multipart form data (type, instructions, optional file). Returns raw markdown and a list of `changed_sections`. Does *not* save to the database.
* **`POST /build-doc`**: (Step 2) Accepts markdown and doc metadata. Uses `doc_builder.py` to create the `.docx`, persists the `Document` record in SQLite, and returns the file stream.
* **`POST /regenerate-section`**: Accepts a section name and targeted instructions. Uses an LLM sub-prompt to rewrite only that specific section.
* **`GET /documents/{doc_id}/diff/{prev_id}`**: Executes a sequence-matching algorithm (Myers diff) on two markdown strings, returning an array of added/removed/unchanged lines for the frontend to render.
* **`POST /documents/{doc_id}/ai-review`**: Triggers a secondary LLM pass using `review_checker.py` to find contradictions or completeness gaps, saving them as comments.

### Backend: Core Services (`services/`)
* **`llm_service.py -> generate_document()`**: Constructs the massive context prompt and handles the network call to Ollama. Includes logic to parse out `CHANGED_SECTIONS` tags from the AI's response.
* **`doc_builder.py -> build_docx()`**: Translates markdown into Word XML. Applies brand hex codes (`#1A3C5E`), sets Calibri fonts, handles pagination, and constructs branded title pages.
* **`auth_service.py -> get_current_user()`**: A FastAPI dependency injected into protected routes to validate JWTs and enforce Role-Based Access Control (RBAC).

### Frontend: Key Components (`src/components/`)
* **`DocForm.jsx`**: The main intake form. Manages complex local state and persists input to `sessionStorage`. Prevents data loss if the user navigates away before generating.
* **`PreviewPanel.jsx`**: The universal document viewer. Features a dual-mode architecture:
  * *Draft Mode:* Allows inline markdown editing and section regeneration. Shows the "Confirm" button.
  * *View Mode:* Read-only view for saved/historical documents. Exposes tabs for Comments, AI Review, Compliance, and Workflow Status. Shows the "Download" button.
  * *Custom Markdown Parser:* Contains a lightweight, custom React parser that translates markdown (`#`, `*`, `|---|`) into styled React DOM elements without relying on heavy HTML injection libraries.
* **`DocHistory.jsx`**: Fetches and filters the history list. Dispatches an action to load an existing document's markdown directly into the `PreviewPanel`'s View Mode.
* **`VersionHistory.jsx`**: A modal component that fetches an entire document group, automatically selects the two most recent versions, and visually renders the diff API response using color-coded rows (green for additions, red for deletions).
* **`api.js`**: Centralized service layer. Wraps the native `fetch` API. It handles JSON parsing, blob extraction for file downloads, and standardizes error throwing for the UI to catch.

