# DocGen — AI-Powered Document Generator

An internal web application for implementation teams to generate professional, brand-consistent documents using a **local LLM (Ollama)**. No data leaves your network.

---

## Features

### Phase 1 — Core Generation
- Select document type: BRD, FSD, SRS, User Manual, Product Brochure
- Enter plain-text instructions; receive a branded `.docx` download
- SQLite document history with type, version, and timestamp

### Phase 2 — Smart Updates & Collaboration
- **Two-step generation**: LLM preview → review/edit markdown → build final file
- **Upload previous version** (.docx or .pdf) for diff-aware regeneration
- **Inline section regeneration** — click ⟳ next to any heading to rewrite just that section
- **Review workflow** — Draft → In Review → Approved / Rejected status pipeline
- **Section comments** — tag comments to document sections; resolve when addressed
- **Version history** — Myers LCS diff view between any two versions of a document
- **Instruction snippets** — save and reuse prompt fragments across sessions

### Phase 3 — Admin, Analytics & Integrations
- **Role-based access** — Admin, Approver, Reviewer, Author (JWT, 24-hour tokens)
- **Admin panel** — edit templates, brand guide, system prompt, and LLM model in-browser
- **Analytics dashboard** — 5 Recharts charts: docs/day, avg generation time, by-type pie, by-status bar, keyword frequency table
- **Notification system** — bell icon with unread badge; auto-triggered on status changes and comments
- **Bulk generation** — select multiple doc types → single `.zip` download with MANIFEST.txt
- **Export formats** — Word (.docx), PDF (reportlab branded), Markdown with YAML frontmatter

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, React Router v6, Recharts |
| Backend | Python 3.11+, FastAPI |
| LLM | Ollama (local) — default model: llama3 |
| Documents | python-docx (Word), reportlab (PDF) |
| File Parsing | python-docx + PyMuPDF |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Storage | SQLite (docgen.db) + local filesystem |

---

## Project Structure

```
docgen/
├── backend/
│   ├── main.py                    # FastAPI app + CORS + lifespan
│   ├── routers/
│   │   ├── generate.py            # /preview-doc, /build-doc, /generate-doc, /generate-bulk
│   │   ├── documents.py           # /documents, /comments, /snippets
│   │   ├── auth.py                # /auth/login, /auth/register, /auth/me
│   │   ├── admin.py               # /admin/* (templates, brand-guide, LLM, users)
│   │   ├── analytics.py           # /analytics/data
│   │   └── notifications.py       # /notifications/*
│   ├── services/
│   │   ├── llm_service.py         # Ollama API calls + CHANGED_SECTIONS parsing
│   │   ├── doc_builder.py         # build_docx(), build_pdf(), build_markdown()
│   │   ├── file_parser.py         # Extract text from .docx/.pdf uploads
│   │   ├── template_loader.py     # Load doc-templates + brand guide
│   │   └── auth_service.py        # JWT creation, password hashing, role guards
│   ├── models/
│   │   ├── database.py            # SQLAlchemy models + migration logic
│   │   └── schemas.py             # Pydantic request/response schemas
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx                # React Router v6 + auth gate
│       ├── main.jsx               # AuthProvider wrapper
│       ├── contexts/
│       │   └── AuthContext.jsx    # JWT state, login/logout, role helpers
│       ├── services/
│       │   └── api.js             # All fetch calls (generation, auth, admin, analytics)
│       ├── components/
│       │   ├── LoginPage.jsx
│       │   ├── DocForm.jsx
│       │   ├── DocHistory.jsx
│       │   ├── PreviewPanel.jsx
│       │   ├── CommentPanel.jsx
│       │   ├── SnippetsPanel.jsx
│       │   ├── VersionHistory.jsx
│       │   ├── AdminPanel.jsx
│       │   ├── AnalyticsDashboard.jsx
│       │   ├── NotificationBell.jsx
│       │   ├── BulkGenerateModal.jsx
│       │   └── Toast.jsx
│       └── styles/
│           └── theme.css
├── doc-templates/                 # One .md file per document type
│   ├── BRD.md
│   ├── FSD.md
│   ├── SRS.md
│   ├── User-Manual.md
│   └── Product-Brochure.md
├── config/
│   └── brand-guide.md             # Brand voice, tone, formatting rules
├── prompts/
│   └── system-prompt.md           # Master LLM system prompt
└── generated_docs/                # Auto-created on first run
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai) running locally with at least one model pulled:
  ```
  ollama pull llama3
  ```

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY to a long random string

# Start the API server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the **first account you register automatically becomes Admin**.

---

## Environment Variables

Create `backend/.env`:

```env
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Database
DATABASE_URL=sqlite:///./docgen.db

# Auth — change this to a long random secret in production
SECRET_KEY=change-me-to-a-long-random-string

# Token lifetime in minutes (default: 1440 = 24 hours)
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

---

## User Roles

| Role | Capabilities |
|---|---|
| **admin** | Everything: templates, brand guide, prompt, LLM model, user management, analytics |
| **approver** | Approve/reject documents, view analytics |
| **reviewer** | Add/resolve comments, move documents to In Review |
| **author** | Generate documents, add comments (read-only workflow actions) |

The first registered user is automatically assigned the **admin** role.
Subsequent registrations default to **author**. Admins can invite users via `POST /auth/register/invite`.

---

## Adding a New Document Type

1. Create a template file in `doc-templates/` — e.g. `doc-templates/Risk-Register.md`
2. Add the type to the dropdown in `frontend/src/components/DocForm.jsx` (the `DOC_TYPES` array)
3. Add it to the bulk generation list in `frontend/src/components/BulkGenerateModal.jsx`
4. Restart the backend (or just reload — templates are read at generation time)

The LLM will use the template structure combined with the brand guide to generate consistent output.

---

## API Reference

### Generation
| Method | Endpoint | Description |
|---|---|---|
| POST | `/preview-doc` | Generate markdown preview (LLM step) |
| POST | `/build-doc` | Build file from markdown + persist to DB |
| POST | `/generate-doc` | Legacy single-step generation |
| POST | `/regenerate-section` | Rewrite one section of an existing document |
| POST | `/generate-bulk` | Generate multiple doc types → `.zip` |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| GET | `/documents` | List documents (filter: doc_type, status, search) |
| GET | `/documents/{id}` | Get single document |
| PATCH | `/documents/{id}/status` | Update workflow status |
| GET | `/documents/group/{group_id}` | Get all versions in a group |
| GET | `/documents/{id}/comments` | List comments |
| POST | `/documents/{id}/comments` | Add comment |
| PATCH | `/comments/{id}/resolve` | Resolve a comment |

### Snippets
| Method | Endpoint | Description |
|---|---|---|
| GET | `/snippets` | List snippets (filter: doc_type, tag) |
| GET | `/snippets/popular` | Top 5 most-used snippets |
| POST | `/snippets` | Create snippet |
| PATCH | `/snippets/{id}/use` | Increment usage count |
| DELETE | `/snippets/{id}` | Delete snippet |

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Self-register (first user → admin) |
| POST | `/auth/register/invite` | Admin-only invite registration |
| POST | `/auth/login` | Login → JWT token |
| GET | `/auth/me` | Current user profile |

### Admin (admin role required)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/templates` | List template files |
| GET/PUT | `/admin/templates/{name}` | Read/write template |
| GET/PUT | `/admin/brand-guide` | Read/write brand guide |
| GET/PUT | `/admin/system-prompt` | Read/write system prompt |
| GET/PUT | `/admin/config/model` | Read/set active LLM model |
| GET | `/admin/users` | List all users |
| DELETE | `/admin/users/{id}` | Delete user |

### Analytics (admin/approver required)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/analytics/data` | All dashboard metrics in one call |

### Notifications
| Method | Endpoint | Description |
|---|---|---|
| GET | `/notifications` | Last 10 notifications |
| GET | `/notifications/unread-count` | Unread badge count |
| PATCH | `/notifications/{id}/read` | Mark one read |
| PATCH | `/notifications/read-all` | Mark all read |

---

## Deployment

### systemd service (Linux)

Create `/etc/systemd/system/docgen-backend.service`:

```ini
[Unit]
Description=DocGen FastAPI Backend
After=network.target

[Service]
User=docgen
WorkingDirectory=/opt/docgen/backend
Environment="PATH=/opt/docgen/backend/venv/bin"
EnvironmentFile=/opt/docgen/backend/.env
ExecStart=/opt/docgen/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable docgen-backend
sudo systemctl start docgen-backend
```

### nginx reverse proxy

```nginx
server {
    listen 80;
    server_name docgen.internal;

    # Frontend (built static files)
    root /opt/docgen/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;   # allow time for LLM generation
        client_max_body_size 20M;  # allow file uploads
    }
}
```

Build the frontend for production:
```bash
cd frontend
npm run build
# Output is in frontend/dist/
```

Update `frontend/src/services/api.js` to use the proxied path:
```js
const BASE_URL = "/api";
```

### Ollama systemd service

Ollama ships with its own installer, but if managing manually:

```ini
[Unit]
Description=Ollama LLM Server
After=network.target

[Service]
User=ollama
ExecStart=/usr/local/bin/ollama serve
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Backup Strategy

DocGen's state lives in two places:

### 1. SQLite database (`backend/docgen.db`)

Schedule a daily backup:
```bash
# /etc/cron.daily/docgen-backup
#!/bin/bash
BACKUP_DIR=/opt/backups/docgen
mkdir -p $BACKUP_DIR
sqlite3 /opt/docgen/backend/docgen.db ".backup $BACKUP_DIR/docgen-$(date +%Y%m%d).db"
# Keep 30 days
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
```

### 2. Generated files (`generated_docs/`)

Include in your standard file backup (rsync, Borg, etc.):
```bash
rsync -av /opt/docgen/generated_docs/ backup-server:/backups/docgen/generated_docs/
```

### 3. Config files (templates, brand guide, system prompt)

These are flat files — include in version control or the same rsync job:
```bash
rsync -av /opt/docgen/doc-templates/ /opt/docgen/config/ /opt/docgen/prompts/ \
  backup-server:/backups/docgen/config/
```

---

## Health Check

```
GET /health → {"status": "ok", "version": "3.0.0"}
```

---

## License

Internal use only. Not for redistribution.
