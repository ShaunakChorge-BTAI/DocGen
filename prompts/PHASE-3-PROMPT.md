# Claude Code — Phase 3 Build Prompt

Run this after Phase 2 is fully working. Start a new Claude Code session.

---

Read CLAUDE.md fully. Phases 1 and 2 are complete and working.

Build Phase 3 — Admin, Analytics & Integrations.

## 1. Admin Panel
- Add route `/admin` in frontend (protected, admin role only)
- Template Manager: list all doc-templates, allow editing content in a textarea, save back to file
- Brand Guide Editor: edit brand-guide.md from the UI
- System Prompt Editor: edit prompts/system-prompt.md from the UI
- LLM Model Switcher: dropdown to change OLLAMA_MODEL env var (llama3, mistral, gemma2, etc.)
- Add backend endpoints for all admin operations with role check middleware

## 2. Role-Based Access Control
- Add SQLite table: `users` with: id, name, email, password_hash, role (admin/author/reviewer/approver), created_at
- JWT authentication: POST `/auth/login`, POST `/auth/register` (admin-invite only), GET `/auth/me`
- Middleware: protect all endpoints, check role for sensitive operations
- Frontend: Login page, logout button, show user name and role in header
- Role rules:
  - Author: can create and edit own documents
  - Reviewer: can view all docs, add comments, change status to approved/rejected
  - Approver: can approve documents, same as reviewer
  - Admin: full access including admin panel

## 3. Analytics Dashboard
- Add route `/analytics` in frontend (admin/approver only)
- Charts to display (use Recharts library):
  - Documents generated per day (last 30 days) — line chart
  - Documents by type — pie chart
  - Documents by status — bar chart
  - Top instruction keywords — word cloud or frequency table
  - Average generation time trend — line chart
- Summary cards: Total docs, Docs this week, Avg generation time, Most used doc type
- Add `generation_time_seconds` column to documents table and record it on each generation

## 4. Export Options
- In doc_builder.py, add:
  - `build_pdf(markdown_content)` → convert .docx to PDF using LibreOffice headless or reportlab
  - `build_markdown(markdown_content)` → save as .md file
- Frontend: Add export format selector before download: DOCX (default), PDF, Markdown
- Add export format to generation request

## 5. Notification System
- Add SQLite table: `notifications` with: id, user_id, message, type, read (bool), created_at
- Trigger notifications on: doc status change, new comment, doc approved
- Frontend: Bell icon in header with unread count badge
- Notification dropdown showing last 10 notifications with mark-as-read

## 6. Snippet Library Enhancement
- Make snippets shareable across team (not just personal)
- Add tags to snippets for better organization
- Add usage_count tracking — show "Used 12 times" on each snippet
- Add endpoint: GET `/snippets/popular` → top 5 most used snippets

## 7. Bulk Document Generation
- Add endpoint: POST `/generate-bulk` accepting: project_name, doc_types (array), instructions
- Generates all selected doc types in sequence for same project
- Returns a .zip file containing all generated .docx files
- Frontend: "Bulk Generate" button that opens a modal with checkboxes for doc types

## 8. README & Deployment Guide
- Update README.md with:
  - Full feature list for all 3 phases
  - Production deployment guide (systemd service for backend, nginx for frontend)
  - How to add new document types (template file + register in template_loader.py)
  - Environment variable reference
  - Backup strategy for SQLite and generated files

After completing, verify:
- Login as admin, edit a template, regenerate a doc and confirm changes reflect
- Run bulk generation for BRD + FSD + SRS, download zip, confirm all 3 docs inside
- View analytics dashboard with at least 10 generated documents in history
