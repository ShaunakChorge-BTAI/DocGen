"""
Admin router — file editors, LLM config, user management.
All endpoints require role=admin enforced via require_admin dependency.
"""

import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, User, Config
from models.schemas import FileContent, ModelConfig, UserRecord
from services.auth_service import require_admin
from services.llm_service import AVAILABLE_MODELS

router = APIRouter(prefix="/admin", tags=["admin"])

# ── File-system paths ──────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR   = _BASE / "doc-templates"
BRAND_GUIDE     = _BASE / "config" / "brand-guide.md"
SYSTEM_PROMPT   = _BASE / "prompts" / "system-prompt.md"


def _safe_template_path(name: str) -> Path:
    """Resolve a template filename safely — reject path traversal attempts."""
    safe_name = Path(name).name          # strip any directory components
    if not safe_name.endswith(".md"):
        safe_name = safe_name + ".md"
    path = (TEMPLATES_DIR / safe_name).resolve()
    if not str(path).startswith(str(TEMPLATES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid template name")
    return path


# ── Templates ──────────────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates(_=Depends(require_admin)):
    return [
        {"name": f.stem, "filename": f.name}
        for f in sorted(TEMPLATES_DIR.glob("*.md"))
    ]


@router.get("/templates/{name}")
def get_template(name: str, _=Depends(require_admin)):
    path = _safe_template_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return {"name": path.stem, "content": path.read_text(encoding="utf-8")}


@router.put("/templates/{name}")
def update_template(name: str, body: FileContent, _=Depends(require_admin)):
    path = _safe_template_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    path.write_text(body.content, encoding="utf-8")
    return {"saved": True, "name": path.stem}


# ── Brand Guide ────────────────────────────────────────────────────────────────

@router.get("/brand-guide")
def get_brand_guide(_=Depends(require_admin)):
    return {"content": BRAND_GUIDE.read_text(encoding="utf-8")}


@router.put("/brand-guide")
def update_brand_guide(body: FileContent, _=Depends(require_admin)):
    BRAND_GUIDE.write_text(body.content, encoding="utf-8")
    return {"saved": True}


# ── System Prompt ──────────────────────────────────────────────────────────────

@router.get("/system-prompt")
def get_system_prompt(_=Depends(require_admin)):
    return {"content": SYSTEM_PROMPT.read_text(encoding="utf-8")}


@router.put("/system-prompt")
def update_system_prompt(body: FileContent, _=Depends(require_admin)):
    SYSTEM_PROMPT.write_text(body.content, encoding="utf-8")
    return {"saved": True}


# ── LLM Model config ───────────────────────────────────────────────────────────

@router.get("/config/model")
def get_model(db: Session = Depends(get_db), _=Depends(require_admin)):
    cfg = db.query(Config).filter(Config.key == "ollama_model").first()
    env_default = os.getenv("OLLAMA_MODEL", "llama3")
    current = cfg.value if cfg else env_default
    return {
        "current": current,
        "env_default": env_default,
        "available": AVAILABLE_MODELS,
    }


@router.put("/config/model")
def set_model(body: ModelConfig, db: Session = Depends(get_db), _=Depends(require_admin)):
    cfg = db.query(Config).filter(Config.key == "ollama_model").first()
    if cfg:
        cfg.value = body.model
    else:
        db.add(Config(key="ollama_model", value=body.model))
    db.commit()
    return {"model": body.model, "saved": True}


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserRecord])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(User).order_by(User.created_at).all()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current=Depends(require_admin)):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"deleted": True}
