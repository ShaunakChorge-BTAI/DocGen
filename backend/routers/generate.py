import io
import os
import re
import time
import uuid
import zipfile
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, Document, Config, Project
from models.schemas import PreviewResponse, SectionRegenerateRequest, BulkGenerateRequest
from services.llm_service import generate_document, generate_section
from services.doc_builder import build_docx, build_pdf, build_markdown
from services.file_parser import extract_text
from services.auth_service import get_current_user_optional

router = APIRouter()

GENERATED_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "generated_docs")
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _active_model(db: Session, project_id: int | None = None) -> str | None:
    """Return the active model: project override → admin config → env var."""
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj and proj.preferred_model:
            return proj.preferred_model
    cfg = db.query(Config).filter(Config.key == "ollama_model").first()
    return cfg.value if cfg else None


def _get_project(db: Session, project_id: int | None) -> Project | None:
    if not project_id:
        return None
    return db.query(Project).filter(Project.id == project_id).first()


def _auto_previous_content(db: Session, doc_type: str, project_id: int | None) -> str | None:
    """Fetch the latest stored markdown for doc_type within the project (no upload needed)."""
    if not project_id:
        return None
    prev = (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.doc_type == doc_type)
        .order_by(Document.id.desc())
        .first()
    )
    return prev.markdown_content if prev and prev.markdown_content else None


def _build_file(markdown: str, doc_type: str, version: str, fmt: str):
    """Return (BytesIO, file_extension, media_type) for the requested format."""
    if fmt == "pdf":
        return build_pdf(markdown, doc_type, version), "pdf", "application/pdf"
    if fmt == "md":
        return (
            build_markdown(markdown, doc_type, version),
            "md",
            "text/markdown; charset=utf-8",
        )
    return (
        build_docx(markdown, doc_type, version),
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def _next_version(current: str | None) -> str:
    if not current:
        return "v1.0"
    try:
        parts = current.lstrip("v").split(".")
        return f"v{parts[0]}.{int(parts[1]) + 1}"
    except Exception:
        return "v1.0"


def _persist(
    db: Session,
    doc_type: str,
    instructions: str,
    file_path: str,
    version: str,
    markdown: str,
    group_id: str,
    generation_time: float | None,
    export_format: str,
    user_id: int | None,
    project_id: int | None = None,
) -> Document:
    record = Document(
        doc_type=doc_type,
        instructions=instructions,
        file_path=file_path,
        version=version,
        status="draft",
        document_group_id=group_id,
        markdown_content=markdown,
        generation_time_seconds=generation_time,
        export_format=export_format,
        created_by_id=user_id,
        project_id=project_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── Step 1: LLM Preview ────────────────────────────────────────────────────────

@router.post("/preview-doc", response_model=PreviewResponse)
async def preview_doc(
    doc_type: str = Form(...),
    instructions: str = Form(...),
    project_id: int | None = Form(None),
    previous_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    previous_content = None
    # Explicit upload takes priority; fall back to auto-lookup from project history
    if previous_file and previous_file.filename:
        file_bytes = await previous_file.read()
        try:
            previous_content = extract_text(file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif project_id:
        previous_content = _auto_previous_content(db, doc_type, project_id)

    model = _active_model(db, project_id)

    t0 = time.perf_counter()

    try:
        markdown, changed_sections = generate_document(
            doc_type, instructions, previous_content, model
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")
    
    gen_time = round(time.perf_counter() - t0, 2)

    return PreviewResponse(
        markdown=markdown, 
        changed_sections=changed_sections,
        generation_time_seconds=gen_time
    )


# ── Step 2: Build + persist ────────────────────────────────────────────────────

@router.post("/build-doc")
async def build_doc(
    doc_type: str = Form(...),
    instructions: str = Form(...),
    markdown: str = Form(...),
    group_id: str | None = Form(None),
    export_format: str = Form("docx"),
    generation_time: float | None = Form(None),
    project_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    # Version increments within the project scope (not globally)
    version_query = db.query(Document).filter(Document.doc_type == doc_type)
    if project_id:
        version_query = version_query.filter(Document.project_id == project_id)
    existing = version_query.order_by(Document.id.desc()).first()
    version = _next_version(existing.version if existing else None)
    doc_group_id = group_id or str(uuid.uuid4())

    file_buf, ext, media_type = _build_file(markdown, doc_type, version, export_format)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_type = doc_type.replace(" ", "-")
    filename = f"{safe_type}_{version}_{timestamp}.{ext}"
    file_path = os.path.join(GENERATED_DOCS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_buf.getvalue())

    record = _persist(
        db, doc_type, instructions, file_path, version,
        markdown, doc_group_id, generation_time, export_format,
        current_user.id if current_user else None,
        project_id=project_id,
    )

    file_buf.seek(0)
    return StreamingResponse(
        file_buf,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Id": str(record.id),
            "X-Group-Id": doc_group_id,
            "X-Version": version,
            "Access-Control-Expose-Headers": "Content-Disposition, X-Document-Id, X-Group-Id, X-Version",
        },
    )


# ── Legacy single-step endpoint ────────────────────────────────────────────────

@router.post("/generate-doc")
async def generate_doc(
    doc_type: str = Form(...),
    instructions: str = Form(...),
    previous_file: UploadFile | None = File(None),
    export_format: str = Form("docx"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    previous_content = None
    if previous_file and previous_file.filename:
        file_bytes = await previous_file.read()
        try:
            previous_content = extract_text(file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    model = _active_model(db)
    t0 = time.perf_counter()
    try:
        markdown, _ = generate_document(doc_type, instructions, previous_content, model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")
    gen_time = round(time.perf_counter() - t0, 2)

    existing = (
        db.query(Document)
        .filter(Document.doc_type == doc_type)
        .order_by(Document.id.desc())
        .first()
    )
    version = _next_version(existing.version if existing else None)

    file_buf, ext, media_type = _build_file(markdown, doc_type, version, export_format)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_type = doc_type.replace(" ", "-")
    filename = f"{safe_type}_{version}_{timestamp}.{ext}"
    file_path = os.path.join(GENERATED_DOCS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_buf.getvalue())

    record = _persist(
        db, doc_type, instructions, file_path, version,
        markdown, str(uuid.uuid4()), gen_time, export_format,
        current_user.id if current_user else None,
    )

    file_buf.seek(0)
    return StreamingResponse(
        file_buf,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Document-Id": str(record.id),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Document-Id",
        },
    )


# ── Section-level regeneration ─────────────────────────────────────────────────

@router.post("/regenerate-section")
async def regenerate_section(
    request: SectionRegenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    doc = db.query(Document).filter(Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.markdown_content:
        raise HTTPException(status_code=400, detail="Document has no stored markdown")

    current_section = _extract_section(doc.markdown_content, request.section_name)
    if not current_section:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{request.section_name}' not found",
        )

    model = _active_model(db)
    try:
        new_section_content = generate_section(
            request.section_name, current_section,
            request.new_instructions, doc.doc_type, model,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")

    updated_markdown = _replace_section(
        doc.markdown_content, request.section_name, new_section_content
    )

    if request.preview_only:
        return {"markdown": updated_markdown}
    
    fmt = doc.export_format or "docx"
    file_buf, ext, media_type = _build_file(updated_markdown, doc.doc_type, doc.version, fmt)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_type = doc.doc_type.replace(" ", "-")
    filename = f"{safe_type}_{doc.version}_updated_{timestamp}.{ext}"
    file_path = os.path.join(GENERATED_DOCS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_buf.getvalue())

    doc.file_path = file_path
    doc.markdown_content = updated_markdown
    db.commit()

    file_buf.seek(0)
    return StreamingResponse(
        file_buf,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ── Bulk Generation ────────────────────────────────────────────────────────────

@router.post("/generate-bulk")
async def generate_bulk(
    request: BulkGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Generate multiple document types in one request, returned as a .zip archive."""
    if not request.doc_types:
        raise HTTPException(status_code=400, detail="At least one doc_type is required")

    model = _active_model(db)
    fmt = request.export_format or "docx"
    zip_buffer = io.BytesIO()
    manifest_lines = [f"Project: {request.project_name}", f"Generated: {datetime.utcnow().isoformat()} UTC", ""]

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_type in request.doc_types:
            t0 = time.perf_counter()
            try:
                markdown, _ = generate_document(
                    doc_type, request.instructions, None, model
                )
            except Exception as e:
                manifest_lines.append(f"✗ {doc_type}: generation failed — {e}")
                continue
            gen_time = round(time.perf_counter() - t0, 2)

            existing = (
                db.query(Document)
                .filter(Document.doc_type == doc_type)
                .order_by(Document.id.desc())
                .first()
            )
            version = _next_version(existing.version if existing else None)

            file_buf, ext, _ = _build_file(markdown, doc_type, version, fmt)

            safe_type = doc_type.replace(" ", "-")
            filename = f"{safe_type}_{version}.{ext}"
            zf.writestr(filename, file_buf.getvalue())

            # Persist each generated doc
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            disk_filename = f"{safe_type}_{version}_{timestamp}.{ext}"
            disk_path = os.path.join(GENERATED_DOCS_DIR, disk_filename)
            with open(disk_path, "wb") as f:
                f.write(file_buf.getvalue())

            _persist(
                db, doc_type, request.instructions, disk_path, version,
                markdown, str(uuid.uuid4()), gen_time, fmt,
                current_user.id if current_user else None,
            )
            manifest_lines.append(f"✓ {doc_type} ({version}) — {gen_time:.1f}s")

        # Add a manifest text file inside the zip
        zf.writestr("MANIFEST.txt", "\n".join(manifest_lines))

    zip_buffer.seek(0)
    safe_project = re.sub(r"[^a-zA-Z0-9_-]", "-", request.project_name)
    zip_filename = f"{safe_project}-docs.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ── Section helpers ────────────────────────────────────────────────────────────

def _get_heading(line: str) -> tuple[int, str] | None:
    m = re.match(r"^(#{1,6})\s+(.*)", line)
    return (len(m.group(1)), m.group(2)) if m else None


def _extract_section(markdown: str, section_name: str) -> str | None:
    lines = markdown.split("\n")
    in_section = False
    section_level = None
    section_lines: list[str] = []
    for line in lines:
        h = _get_heading(line)
        if h:
            level, title = h
            if title.strip().lower() == section_name.strip().lower():
                in_section = True
                section_level = level
                section_lines.append(line)
            elif in_section and level <= section_level:
                break
            elif in_section:
                section_lines.append(line)
        elif in_section:
            section_lines.append(line)
    return "\n".join(section_lines) if section_lines else None


def _replace_section(markdown: str, section_name: str, new_content: str) -> str:
    lines = markdown.split("\n")
    result: list[str] = []
    in_section = False
    section_level = None
    replaced = False
    for line in lines:
        h = _get_heading(line)
        if h:
            level, title = h
            if title.strip().lower() == section_name.strip().lower():
                in_section = True
                section_level = level
                result.append(new_content)
                replaced = True
            elif in_section and level <= section_level:
                in_section = False
                result.append(line)
            elif not in_section:
                result.append(line)
        elif not in_section:
            result.append(line)
    if not replaced:
        result.append(new_content)
    return "\n".join(result)
