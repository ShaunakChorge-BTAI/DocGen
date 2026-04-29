import difflib
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from models.database import get_db, Document, Comment, Snippet, Notification, ComplianceScore
from models.schemas import (
    DocumentRecord, StatusUpdate,
    CommentCreate, CommentRecord,
    SnippetCreate, SnippetRecord,
    AIReviewResult, AIReviewIssue,
    ComplianceScoreRequest, ComplianceScoreResult, ComplianceCriterion,
)
from services.auth_service import get_current_user_optional, get_current_user, get_user_project_ids
import services.review_checker as review_checker
import services.compliance_scorer as compliance_scorer

router = APIRouter()

VALID_STATUSES = {"draft", "in_review", "approved", "rejected"}


def _notify(db: Session, message: str, ntype: str, doc_id: int | None = None):
    db.add(Notification(message=message, type=ntype, related_doc_id=doc_id))


def _project_filter(query, current_user, db: Session, project_id: int | None = None):
    """
    Restrict query to documents the current user is allowed to see.
    - If project_id provided: filter to that specific project (membership checked).
    - Otherwise: filter to all projects the user is a member of.
    - Global admin sees everything.
    """
    if current_user is None:
        return query.filter(False)   # unauthenticated — no results
    allowed_ids = get_user_project_ids(current_user, db)
    if project_id is not None:
        if project_id not in allowed_ids and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied to this project")
        return query.filter(Document.project_id == project_id)
    return query.filter(
        (Document.project_id.in_(allowed_ids)) | (Document.project_id == None)  # noqa: E711
    )


# ── Documents ──────────────────────────────────────────────────────────────────

@router.get("/documents", response_model=List[DocumentRecord])
def get_documents(
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    query = db.query(Document)
    query = _project_filter(query, current_user, db, project_id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if status:
        query = query.filter(Document.status == status)
    if search:
        query = query.filter(Document.instructions.contains(search))
    return query.order_by(Document.created_at.desc()).limit(100).all()


@router.get("/documents/group/{group_id}", response_model=List[DocumentRecord])
def get_document_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    query = db.query(Document).filter(Document.document_group_id == group_id)
    query = _project_filter(query, current_user, db)
    return query.order_by(Document.created_at.asc()).all()


@router.get("/documents/{doc_id}", response_model=DocumentRecord)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user:
        allowed = get_user_project_ids(current_user, db)
        if doc.project_id is not None and doc.project_id not in allowed and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
    return doc


@router.patch("/documents/{doc_id}/status")
def update_status(
    doc_id: int,
    update: StatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if update.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}",
        )
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = update.status
    _notify(db, f"{doc.doc_type} status changed to \"{update.status}\"", "status_change", doc_id)
    if update.status == "approved":
        _notify(db, f"{doc.doc_type} has been approved ✓", "doc_approved", doc_id)
    db.commit()
    return {"id": doc.id, "status": doc.status}


# ── Diff endpoint (approver comparative view) ──────────────────────────────────

@router.get("/documents/{doc_id}/diff/{prev_id}")
def get_diff(
    doc_id: int,
    prev_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """
    Return a line-level diff between two document versions.
    Each entry: {"type": "added"|"removed"|"unchanged", "content": "..."}
    """
    new_doc = db.query(Document).filter(Document.id == doc_id).first()
    old_doc = db.query(Document).filter(Document.id == prev_id).first()
    if not new_doc or not old_doc:
        raise HTTPException(status_code=404, detail="One or both documents not found")
    if not new_doc.markdown_content or not old_doc.markdown_content:
        raise HTTPException(status_code=400, detail="Both documents must have stored markdown content")

    old_lines = old_doc.markdown_content.splitlines(keepends=True)
    new_lines = new_doc.markdown_content.splitlines(keepends=True)
    result = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for line in old_lines[i1:i2]:
                result.append({"type": "unchanged", "content": line.rstrip()})
        elif opcode in ("replace", "delete"):
            for line in old_lines[i1:i2]:
                result.append({"type": "removed", "content": line.rstrip()})
        if opcode in ("replace", "insert"):
            for line in new_lines[j1:j2]:
                result.append({"type": "added", "content": line.rstrip()})

    return {
        "old_version": old_doc.version,
        "new_version": new_doc.version,
        "old_doc_type": old_doc.doc_type,
        "diff": result,
        "stats": {
            "added": sum(1 for d in result if d["type"] == "added"),
            "removed": sum(1 for d in result if d["type"] == "removed"),
            "unchanged": sum(1 for d in result if d["type"] == "unchanged"),
        },
    }


# ── Comments ───────────────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/comments", response_model=List[CommentRecord])
def get_comments(doc_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    return db.query(Comment).filter(Comment.document_id == doc_id).order_by(Comment.created_at.asc()).all()


@router.post("/documents/{doc_id}/comments", response_model=CommentRecord)
def add_comment(
    doc_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    author_name = comment.author or (current_user.name if current_user else "User")
    record = Comment(
        document_id=doc_id,
        section_name=comment.section_name,
        comment_text=comment.comment_text,
        author=author_name,
    )
    db.add(record)
    _notify(db, f"New comment on {doc.doc_type} [{comment.section_name}] by {author_name}", "comment_added", doc_id)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/comments/{comment_id}/resolve")
def resolve_comment(comment_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.resolved = True
    db.commit()
    return {"id": comment.id, "resolved": True}


# ── Snippets ───────────────────────────────────────────────────────────────────

@router.get("/snippets/popular", response_model=List[SnippetRecord])
def get_popular_snippets(
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    query = db.query(Snippet)
    if project_id:
        query = query.filter((Snippet.project_id == project_id) | (Snippet.project_id == None))  # noqa: E711
    return query.order_by(Snippet.usage_count.desc()).limit(5).all()


@router.get("/snippets", response_model=List[SnippetRecord])
def get_snippets(
    doc_type: Optional[str] = None,
    tag: Optional[str] = None,
    project_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    query = db.query(Snippet)
    if project_id:
        query = query.filter((Snippet.project_id == project_id) | (Snippet.project_id == None))  # noqa: E711
    if doc_type:
        query = query.filter((Snippet.doc_type == doc_type) | (Snippet.doc_type == None))  # noqa: E711
    if tag:
        query = query.filter(Snippet.tags.contains(tag))
    return query.order_by(Snippet.usage_count.desc(), Snippet.created_at.desc()).all()


@router.post("/snippets", response_model=SnippetRecord)
def create_snippet(
    snippet: SnippetCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    record = Snippet(title=snippet.title, content=snippet.content, doc_type=snippet.doc_type, tags=snippet.tags)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/snippets/{snippet_id}/use")
def use_snippet(snippet_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    snippet = db.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    snippet.usage_count += 1
    db.commit()
    return {"id": snippet.id, "usage_count": snippet.usage_count}


@router.delete("/snippets/{snippet_id}")
def delete_snippet(snippet_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    snippet = db.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    db.delete(snippet)
    db.commit()
    return {"deleted": True}


# ── AI Review ──────────────────────────────────────────────────────────────────

def _active_model_docs(db: Session) -> str | None:
    from models.database import Config
    cfg = db.query(Config).filter(Config.key == "ollama_model").first()
    return cfg.value if cfg else None


@router.post("/documents/{doc_id}/ai-review", response_model=AIReviewResult)
def run_ai_review(
    doc_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.markdown_content:
        raise HTTPException(status_code=400, detail="Document has no stored markdown content")

    model = _active_model_docs(db)
    try:
        issues = review_checker.run_ai_review(doc.doc_type, doc.markdown_content, model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI review failed: {e}")

    created_comments = []
    for issue in issues:
        label = issue["issue_type"].replace("_", " ").title()
        comment = Comment(
            document_id=doc_id,
            section_name=issue["section"],
            comment_text=f"[{label}] {issue['description']}",
            author="AI Reviewer",
        )
        db.add(comment)
        created_comments.append(comment)

    _notify(db, f"AI review: {len(issues)} issue(s) found in {doc.doc_type}", "ai_review", doc_id)
    db.commit()
    for c in created_comments:
        db.refresh(c)

    return AIReviewResult(
        doc_id=doc_id,
        issues=[AIReviewIssue(**i) for i in issues],
        comments_created=len(created_comments),
    )


# ── Compliance Scoring ─────────────────────────────────────────────────────────

@router.get("/compliance-rubrics")
def list_rubrics(_=Depends(get_current_user_optional)):
    return {"rubrics": compliance_scorer.list_rubrics()}


@router.get("/documents/{doc_id}/compliance-scores")
def get_compliance_scores(doc_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    scores = (
        db.query(ComplianceScore)
        .filter(ComplianceScore.document_id == doc_id)
        .order_by(ComplianceScore.scored_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "doc_id": doc_id,
            "rubric": s.rubric_name,
            "score": s.score,
            "criteria": json.loads(s.criteria_json),
            "scored_at": s.scored_at.isoformat(),
        }
        for s in scores
    ]


@router.post("/documents/{doc_id}/compliance-score")
def run_compliance_score(
    doc_id: int,
    request: ComplianceScoreRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user_optional),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.markdown_content:
        raise HTTPException(status_code=400, detail="Document has no stored markdown content")

    model = _active_model_docs(db)
    try:
        result = compliance_scorer.score_document(doc.doc_type, doc.markdown_content, request.rubric_name, model)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scoring failed: {e}")

    record = ComplianceScore(
        document_id=doc_id,
        rubric_name=request.rubric_name,
        score=result["score"],
        criteria_json=json.dumps(result.get("criteria", [])),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "doc_id": doc_id,
        "rubric": request.rubric_name,
        "score": result["score"],
        "criteria": result.get("criteria", []),
        "scored_at": record.scored_at.isoformat(),
    }
