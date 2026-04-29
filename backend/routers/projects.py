import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, Project, ProjectMember, UploadedImage, User
from models.schemas import (
    ProjectCreate, ProjectUpdate, ProjectRecord,
    ProjectMemberCreate, ProjectMemberRecord,
    UploadedImageRecord,
)
from services.auth_service import get_current_user, get_user_project_ids

router = APIRouter()

UPLOADS_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
LOGOS_DIR    = os.path.join(UPLOADS_BASE, "logos")
IMAGES_DIR   = os.path.join(UPLOADS_BASE, "images")

_ALLOWED_IMG_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
_MAX_LOGO_BYTES    = 2 * 1024 * 1024   # 2 MB


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_project_or_404(project_id: int, db: Session) -> Project:
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _assert_member(project_id: int, user: User, db: Session, roles: tuple = ()) -> ProjectMember:
    if user.role == "admin":
        return None
    m = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id,
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="You are not a member of this project")
    if roles and m.role not in roles:
        raise HTTPException(status_code=403, detail=f"Requires role: {' or '.join(roles)}")
    return m


def _member_with_user(m: ProjectMember, db: Session) -> dict:
    user = db.query(User).filter(User.id == m.user_id).first()
    return {
        "id": m.id,
        "project_id": m.project_id,
        "user_id": m.user_id,
        "role": m.role,
        "joined_at": m.joined_at,
        "user_name": user.name if user else None,
        "user_email": user.email if user else None,
    }


# ── Project CRUD ───────────────────────────────────────────────────────────────

@router.post("", response_model=ProjectRecord, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if db.query(Project).filter(Project.code == payload.code.upper()).first():
        raise HTTPException(status_code=409, detail=f"Project code '{payload.code}' already exists")
    project = Project(
        code=payload.code.upper(),
        name=payload.name,
        description=payload.description,
        client_name=payload.client_name,
        preferred_model=payload.preferred_model,
        status="active",
        created_by_id=current_user.id,
    )
    db.add(project)
    db.flush()   # get project.id before commit
    # Creator automatically becomes owner
    db.add(ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="owner",
    ))
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectRecord])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_ids = get_user_project_ids(current_user, db)
    return (
        db.query(Project)
        .filter(Project.id.in_(project_ids))
        .order_by(Project.created_at.desc())
        .all()
    )


@router.get("/{project_id}", response_model=ProjectRecord)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db)
    return project


@router.put("/{project_id}", response_model=ProjectRecord)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db, roles=("owner",))
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(project, field, val)
    db.commit()
    db.refresh(project)
    return project


# ── Member Management ──────────────────────────────────────────────────────────

@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db)
    members = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    return [_member_with_user(m, db) for m in members]


@router.post("/{project_id}/members", status_code=201)
def add_member(
    project_id: int,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db, roles=("owner",))
    if not db.query(User).filter(User.id == payload.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == payload.user_id,
    ).first()
    if existing:
        existing.role = payload.role
        db.commit()
        return _member_with_user(existing, db)
    member = ProjectMember(project_id=project_id, user_id=payload.user_id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_with_user(member, db)


@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db, roles=("owner",))
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        owners = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "owner",
        ).count()
        if owners <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last project owner")
    db.delete(member)
    db.commit()
    return {"deleted": True}


# ── Logo Upload ────────────────────────────────────────────────────────────────

def _save_logo(project_id: int, logo_type: str, file: UploadFile) -> str:
    os.makedirs(LOGOS_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    filename = f"proj{project_id:04d}_{logo_type}{ext}"
    dest = os.path.join(LOGOS_DIR, filename)
    content = file.file.read()
    if len(content) > _MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Logo file too large (max 2 MB)")
    if file.content_type and file.content_type not in _ALLOWED_IMG_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    with open(dest, "wb") as f:
        f.write(content)
    return dest


@router.post("/{project_id}/logo/company")
def upload_company_logo(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db, roles=("owner",))
    path = _save_logo(project_id, "company", file)
    project.company_logo_path = path
    db.commit()
    return {"company_logo_path": path}


@router.post("/{project_id}/logo/client")
def upload_client_logo(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db, roles=("owner",))
    path = _save_logo(project_id, "client", file)
    project.client_logo_path = path
    db.commit()
    return {"client_logo_path": path}


# ── Image Upload (for User Manual body content) ────────────────────────────────

@router.post("/{project_id}/images", response_model=UploadedImageRecord, status_code=201)
def upload_image(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db)
    if file.content_type and file.content_type not in _ALLOWED_IMG_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    proj_img_dir = os.path.join(IMAGES_DIR, f"proj{project_id:04d}")
    os.makedirs(proj_img_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(proj_img_dir, unique_name)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    record = UploadedImage(
        project_id=project_id,
        filename=file.filename or unique_name,
        file_path=dest,
        uploaded_by=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{project_id}/images", response_model=List[UploadedImageRecord])
def list_images(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    _assert_member(project_id, current_user, db)
    return (
        db.query(UploadedImage)
        .filter(UploadedImage.project_id == project_id)
        .order_by(UploadedImage.created_at.desc())
        .all()
    )
