# Claude Code — Phase 2 Build Prompt

Run this after Phase 1 is fully working. Start a new Claude Code session.

---

Read CLAUDE.md fully. Phase 1 is complete and working.

Build Phase 2 — Collaboration, Smart Updates & Review Workflow.

## 1. Diff-Aware Document Regeneration
- In `llm_service.py`, when `previous_content` is provided, modify the prompt to instruct the LLM to:
  - Identify which sections are affected by the user's change instructions
  - Preserve all unaffected sections exactly from the previous version
  - Only rewrite the relevant sections
- Add a `changed_sections` field to the document response so the frontend can highlight what changed

## 2. Section-Level Regeneration
- Add endpoint: POST `/regenerate-section` with: `document_id`, `section_name`, `new_instructions`
- Returns updated .docx with only that section replaced
- Frontend: Add a "Regenerate this section" button next to each major heading in PreviewPanel

## 3. Document Status Workflow
- Update SQLite `documents` table to add: `status` column (draft, in_review, approved, rejected)
- Add endpoint: PATCH `/documents/{id}/status` to update status
- Add endpoint: GET `/documents/{id}` to get single document with full details
- Frontend: Show status badge on each document in history (color-coded)
- Add status change buttons: "Send for Review", "Approve", "Reject" with confirmation dialog

## 4. Inline Comments
- Add SQLite table: `comments` with: id, document_id, section_name, comment_text, author, created_at, resolved (bool)
- Add endpoint: POST `/documents/{id}/comments`
- Add endpoint: GET `/documents/{id}/comments`
- Add endpoint: PATCH `/comments/{id}/resolve`
- Frontend: Add comment panel in PreviewPanel showing comments per section, ability to add and resolve

## 5. Version History & Comparison
- Every generation saves as a new version linked to same `document_group_id`
- Add endpoint: GET `/documents/group/{group_id}` to list all versions
- Frontend: Add "Version History" tab in DocHistory showing all versions of a document
- Add side-by-side diff view comparing two versions (highlight additions in green, removals in red)

## 6. Reusable Instruction Snippets
- Add SQLite table: `snippets` with: id, title, content, doc_type, usage_count, created_at
- Add endpoints: GET `/snippets`, POST `/snippets`, DELETE `/snippets/{id}`
- Frontend: Below the instructions textarea, show a "Saved Snippets" panel
- Clicking a snippet appends it to the instructions textarea
- After generation, offer "Save these instructions as a snippet" button

## 7. Generation Preview Enhancement
- After LLM generates markdown, send it back to frontend as plain text first
- Display a scrollable markdown preview in PreviewPanel before the .docx is built
- User confirms → triggers .docx build and download
- Add "Edit before downloading" — allow user to edit the raw markdown in a textarea and then build .docx from edited version

## 8. UI Improvements
- Add document search bar in DocHistory (filter by doc_type, date range, status)
- Add toast notifications for: generation complete, status changed, comment added
- Add keyboard shortcut: Ctrl+Enter to submit the form
- Make layout responsive for tablet (768px+)

After completing, verify:
- Upload a previous .docx, enter change instructions, confirm only relevant sections change
- Change document status through full workflow: draft → in_review → approved
- Add a comment, resolve it, verify it disappears from active comments
- Save a snippet, reuse it in next generation
