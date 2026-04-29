# DocGen — AI-Powered Document Generator
## Master Context for Claude Code

---

## Purpose
An internal web application for implementation teams to generate professional, brand-consistent documents using a local LLM (Ollama). No data leaves the organization.

## User Workflow
1. Select document type (BRD, FSD, SRS, User Manual, Product Brochure)
2. Optionally upload a previous version (.docx or .pdf)
3. Enter change instructions or idea in plain text
4. Click Generate → Download branded .docx file

---

## Tech Stack
- **Frontend:** React (Vite) — single page, clean professional UI
- **Backend:** Python FastAPI
- **LLM:** Ollama (local) at http://localhost:11434/api/generate — default model: llama3
- **Document Output:** python-docx with branded formatting
- **File Parsing:** python-docx + PyMuPDF (for PDF extraction)
- **Version Storage:** SQLite (lightweight, no external DB needed)
- **Auth:** Simple JWT-based login (no SSO in Phase 1)

---

## Project Structure
```
/backend
  main.py                  # FastAPI app entry point
  routers/
    generate.py            # POST /generate-doc
    documents.py           # GET /documents (history)
    auth.py                # POST /login, /register
  services/
    llm_service.py         # Ollama API calls
    doc_builder.py         # python-docx branded output
    file_parser.py         # Extract text from .docx/.pdf uploads
    template_loader.py     # Load doc-templates + brand guide
  models/
    database.py            # SQLite setup
    schemas.py             # Pydantic models
  utils/
    diff_helper.py         # Compare old vs new version content

/frontend
  src/
    App.jsx
    components/
      DocForm.jsx           # Main form: type selector, upload, instructions
      DocHistory.jsx        # List of previously generated docs
      PreviewPanel.jsx      # Show generated content summary before download
      LoadingSpinner.jsx
    services/
      api.js                # Axios calls to backend
    styles/
      theme.css             # Brand colors and fonts

/doc-templates              # One .md file per document type
/config
  brand-guide.md            # Brand voice, tone, formatting rules
/prompts
  system-prompt.md          # Master LLM system prompt
```

---

## Key Rules for Claude Code
1. Always read `/config/brand-guide.md` before generating any document
2. Always load the matching template from `/doc-templates/` based on doc_type
3. If a previous version is uploaded, extract its text and include as "Previous Version" context in the LLM prompt
4. Apply diff logic — instruct LLM to only update sections relevant to the change instructions
5. Output must always be a downloadable branded `.docx` file
6. Store every generation in SQLite with: doc_type, instructions, timestamp, file_path, version_number
7. Show a content preview summary on frontend before the download button appears
8. Never call external APIs — all LLM calls go to local Ollama only

---

## Phases
### Phase 1 (Build First)
- Core form UI
- FastAPI backend with /generate-doc endpoint
- Ollama integration
- Branded .docx output
- Basic document history (SQLite)

### Phase 2 (Build After Phase 1 Works)
- Upload + parse previous version
- Diff-aware regeneration (only changed sections)
- Review & approval workflow (Draft → Review → Approved)
- Inline section-level regeneration buttons
- Version comparison view

### Phase 3 (Workflow Intelligence)
- Role-based access (Author, Reviewer, Approver)
- Slack/email notifications on doc status change
- Reusable instruction snippet library
- Admin panel: edit templates and brand guide from UI
- Analytics dashboard: docs generated, time saved
- Export to PDF, Markdown, Confluence
- **AI-assisted review comments** — second Ollama pass checks for completeness gaps, contradictions, and missing requirements before human review (`services/review_checker.py`)
- **Document compliance scoring** — score docs against rubrics (ISO 9001, internal standards) before they enter approval; flag gaps automatically (`services/compliance_scorer.py`, `/config/rubrics/`)
- **Email & Slack notification delivery** — extend in-app notifications to send via SMTP and Slack webhooks on status changes and approvals (`services/email_service.py`, `services/slack_service.py`)
- **Confluence export** — push approved documents to Confluence as pages via REST API (`services/confluence_service.py`)

### Phase 4 (Integrations & Intake Expansion)
- **Jira / Azure DevOps sync** — auto-generate user stories from approved BRDs and push to backlog via local API integration (`services/backlog_sync.py`, `/config/integrations.yaml`)
- **RAG-powered context injection** — local vector DB (ChromaDB) indexes past projects, meeting notes, client briefs; retrieval-augmented prompts eliminate placeholder content (`services/rag_service.py`, `/vector-store/`)
- **Voice-to-document intake** — record requirements walkthroughs, transcribe locally via Whisper, feed structured output to doc generation; turns a 45-min meeting into a first-draft BRD (`services/voice_intake.py`, Whisper local model)
- **Multi-language output** — parallel Ollama calls generate the same document in multiple languages from one source; no third-party translation service (`services/multilang_service.py`)

### Phase 5 (Domain Adaptation)
- **Fine-tuned domain models** — train lightweight LoRA adapters on the organisation's accumulated generated documents (from Phases 1–4) so outputs match internal voice and terminology out of the box (`/training/`, `services/lora_manager.py`)
- Requires: curated training corpus from Phase 4 doc history, GPU-capable local machine or on-prem server

---

## Environment Variables (backend/.env)
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
DATABASE_URL=sqlite:///./docgen.db
SECRET_KEY=your-secret-key-here
```

---

## Do Not
- Do not use external LLM APIs (OpenAI, Anthropic, etc.)
- Do not use PostgreSQL or MySQL in Phase 1
- Do not add heavy UI libraries — keep frontend lean
- Do not store files in cloud — all local file system storage
