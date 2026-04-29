# Claude Code — Phase 1 Build Prompt

Paste this entire prompt into Claude Code after running `claude` in the project root.

---

Read CLAUDE.md fully before writing any code.

Build Phase 1 of the DocGen application. Complete all of the following in one session:

## Backend (FastAPI)

1. Create `backend/main.py` as the FastAPI entry point with CORS enabled for localhost:5173

2. Create `backend/routers/generate.py` with:
   - POST `/generate-doc` endpoint
   - Accepts multipart form: `doc_type` (str), `instructions` (str), `previous_file` (optional UploadFile)
   - Returns a `.docx` file as StreamingResponse with filename header

3. Create `backend/services/template_loader.py`:
   - Function `load_template(doc_type)` → reads matching file from `/doc-templates/`
   - Function `load_brand_guide()` → reads `/config/brand-guide.md`
   - Function `load_system_prompt()` → reads `/prompts/system-prompt.md`
   - Map doc_type values: "BRD", "FSD", "SRS", "User Manual", "Product Brochure" to correct filenames

4. Create `backend/services/file_parser.py`:
   - Function `extract_text_from_docx(file_bytes)` → returns plain text using python-docx
   - Function `extract_text_from_pdf(file_bytes)` → returns plain text using PyMuPDF (fitz)
   - Auto-detect file type from bytes and call correct function

5. Create `backend/services/llm_service.py`:
   - Function `generate_document(doc_type, instructions, previous_content=None)` → returns markdown string
   - Calls Ollama at `http://localhost:11434/api/generate` with model from env var
   - Constructs prompt by combining: system_prompt + brand_guide + template + instructions + previous_content
   - Streams response and returns full assembled text

6. Create `backend/services/doc_builder.py`:
   - Function `build_docx(markdown_content, doc_type)` → returns BytesIO object
   - Parse markdown headings (#, ##, ###) and apply correct Word styles and font sizes from brand guide
   - Apply brand colors: H1 = #1A3C5E, H2 = #2E7DB2
   - Parse markdown tables and render as Word tables with header row styling (bg: #E8F4FD, bold)
   - Set font to Calibri, body 11pt, margins 2.5cm all sides, line spacing 1.15
   - Add header on each page: doc_type left, version right
   - Add footer on each page: "Company Name | doc_type | Version | Page X of Y" + confidentiality notice

7. Create `backend/models/database.py`:
   - SQLite setup using SQLAlchemy
   - Table: `documents` with columns: id, doc_type, instructions, file_path, version, created_at, status (default: "completed")

8. Create `backend/models/schemas.py` with Pydantic models for request/response

9. Create `backend/routers/documents.py`:
   - GET `/documents` → returns list of last 50 generated documents from SQLite

10. Create `backend/.env` with:
    ```
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_MODEL=llama3
    DATABASE_URL=sqlite:///./docgen.db
    SECRET_KEY=docgen-secret-2024
    ```

11. Create `backend/requirements.txt`:
    ```
    fastapi
    uvicorn
    python-docx
    PyMuPDF
    python-dotenv
    sqlalchemy
    python-multipart
    httpx
    ```

---

## Frontend (React + Vite)

12. Initialize Vite React project in `/frontend` if not already done

13. Create `frontend/src/App.jsx`:
    - Two-panel layout: left = form, right = history/preview
    - Import and render DocForm and DocHistory components

14. Create `frontend/src/components/DocForm.jsx`:
    - Dropdown: Document Type (BRD, FSD, SRS, User Manual, Product Brochure)
    - Textarea: Instructions / Change Description (placeholder: "Describe what you want in this document...")
    - File upload: Previous Version (accept .docx, .pdf only) — optional
    - Submit button: "Generate Document"
    - On submit: POST to http://localhost:8000/generate-doc as FormData
    - Show LoadingSpinner while waiting
    - On success: show PreviewPanel with download button
    - On error: show clear error message

15. Create `frontend/src/components/PreviewPanel.jsx`:
    - Show: doc type, generation timestamp, a summary message ("Your [doc_type] is ready")
    - Large download button that triggers file download
    - "Generate Another" button that resets the form

16. Create `frontend/src/components/DocHistory.jsx`:
    - Fetch GET http://localhost:8000/documents on mount
    - Display list of last 20 docs: doc_type, date, instructions snippet, download icon
    - Refresh after each new generation

17. Create `frontend/src/components/LoadingSpinner.jsx`:
    - Simple animated spinner with message: "Generating your document..."

18. Create `frontend/src/services/api.js`:
    - `generateDoc(formData)` → POST /generate-doc, returns blob
    - `getDocuments()` → GET /documents, returns JSON

19. Create `frontend/src/styles/theme.css`:
    - CSS variables: --primary: #1A3C5E, --secondary: #2E7DB2, --accent: #E8F4FD
    - Clean professional UI, white background, subtle shadows on cards
    - Responsive for desktop (min 1024px)

---

## Final Steps

20. Create `run.sh` in project root:
    ```bash
    #!/bin/bash
    echo "Starting DocGen..."
    cd backend && uvicorn main:app --reload --port 8000 &
    cd frontend && npm run dev &
    echo "Backend: http://localhost:8000"
    echo "Frontend: http://localhost:5173"
    ```

21. Create `README.md` with:
    - Prerequisites (Python 3.10+, Node 18+, Ollama installed with llama3 pulled)
    - Setup steps
    - How to run
    - How to customize templates and brand guide

After completing all steps, verify:
- Backend starts without errors: `cd backend && uvicorn main:app --reload`
- Frontend starts without errors: `cd frontend && npm run dev`
- Test a BRD generation end-to-end with sample instructions
