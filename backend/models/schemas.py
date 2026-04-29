from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List


# ── Documents ──────────────────────────────────────────────────────────────────

class DocumentRecord(BaseModel):
    id: int
    doc_type: str
    instructions: str
    file_path: Optional[str] = None
    version: str
    created_at: datetime
    status: str
    document_group_id: Optional[str] = None
    markdown_content: Optional[str] = None
    generation_time_seconds: Optional[float] = None
    created_by_id: Optional[int] = None
    export_format: Optional[str] = "docx"
    project_id: Optional[int] = None

    class Config:
        from_attributes = True


class PreviewResponse(BaseModel):
    markdown: str
    changed_sections: List[str]


class StatusUpdate(BaseModel):
    status: str


class SectionRegenerateRequest(BaseModel):
    document_id: int
    section_name: str
    new_instructions: str
    preview_only: Optional[bool] = False


# ── Comments ───────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    section_name: str
    comment_text: str
    author: Optional[str] = "User"


class CommentRecord(BaseModel):
    id: int
    document_id: int
    section_name: str
    comment_text: str
    author: str
    created_at: datetime
    resolved: bool

    class Config:
        from_attributes = True


# ── Snippets ───────────────────────────────────────────────────────────────────

class SnippetCreate(BaseModel):
    title: str
    content: str
    doc_type: Optional[str] = None
    tags: Optional[str] = None   # comma-separated


class SnippetRecord(BaseModel):
    id: int
    title: str
    content: str
    doc_type: Optional[str] = None
    usage_count: int
    created_at: datetime
    tags: Optional[str] = None

    class Config:
        from_attributes = True


# ── Auth ───────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "author"   # admin can override when creating users


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRecord(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Notifications ──────────────────────────────────────────────────────────────

class NotificationRecord(BaseModel):
    id: int
    message: str
    type: str
    read: bool
    created_at: datetime
    related_doc_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── Analytics ──────────────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_docs: int
    docs_this_week: int
    avg_generation_time: Optional[float]
    most_used_type: Optional[str]


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    docs_per_day: List[dict]
    by_type: List[dict]
    by_status: List[dict]
    top_keywords: List[dict]
    avg_time_per_day: List[dict]


# ── Projects ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    preferred_model: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    preferred_model: Optional[str] = None
    status: Optional[str] = None


class ProjectRecord(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    company_logo_path: Optional[str] = None
    client_logo_path: Optional[str] = None
    preferred_model: Optional[str] = None
    status: str
    created_at: datetime
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class ProjectMemberCreate(BaseModel):
    user_id: int
    role: str   # owner | author | reviewer | approver


class ProjectMemberRecord(BaseModel):
    id: int
    project_id: int
    user_id: int
    role: str
    joined_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True


class UploadedImageRecord(BaseModel):
    id: int
    project_id: int
    filename: str
    file_path: str
    uploaded_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI Review ─────────────────────────────────────────────────────────────────

class AIReviewIssue(BaseModel):
    section: str
    issue_type: str
    description: str


class AIReviewResult(BaseModel):
    doc_id: int
    issues: List[AIReviewIssue]
    comments_created: int


# ── Compliance Scoring ─────────────────────────────────────────────────────────

class ComplianceScoreRequest(BaseModel):
    rubric_name: str


class ComplianceCriterion(BaseModel):
    criterion: str
    status: str
    note: str


class ComplianceScoreResult(BaseModel):
    id: int
    doc_id: int
    rubric: str
    score: int
    criteria: List[ComplianceCriterion]
    scored_at: str


# ── Bulk Generation ────────────────────────────────────────────────────────────

class BulkGenerateRequest(BaseModel):
    project_name: str
    doc_types: List[str]
    instructions: str
    export_format: str = "docx"


# ── Admin ──────────────────────────────────────────────────────────────────────

class FileContent(BaseModel):
    content: str


class ModelConfig(BaseModel):
    model: str
