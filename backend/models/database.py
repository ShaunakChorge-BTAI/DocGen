from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    Text, Boolean, Float, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./docgen.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="author")   # admin | author | reviewer | approver
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # e.g. "PROJ001"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(200), nullable=True)
    company_logo_path = Column(String(500), nullable=True)   # relative path under uploads/logos/
    client_logo_path = Column(String(500), nullable=True)
    preferred_model = Column(String(100), nullable=True)     # per-project LLM override
    status = Column(String(20), default="active")            # active | archived
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(30), nullable=False)    # owner | author | reviewer | approver
    joined_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        Index("ix_project_members_user", "user_id"),
    )


class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_type = Column(String, nullable=False)
    instructions = Column(Text, nullable=False)
    file_path = Column(String, nullable=True)
    version = Column(String, default="v1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="draft")
    document_group_id = Column(String, nullable=True)
    markdown_content = Column(Text, nullable=True)
    generation_time_seconds = Column(Float, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    export_format = Column(String, default="docx")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    __table_args__ = (
        Index("ix_documents_project_type",   "project_id", "doc_type"),
        Index("ix_documents_project_status", "project_id", "status"),
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    section_name = Column(String, nullable=False)
    comment_text = Column(Text, nullable=False)
    author = Column(String, default="User")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)


class Snippet(Base):
    __tablename__ = "snippets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    doc_type = Column(String, nullable=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    tags = Column(String, nullable=True)   # comma-separated, e.g. "finance,scope"
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # NULL = global


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False)   # status_change | comment_added | doc_approved
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    related_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)


class Config(Base):
    """Key-value store for runtime configuration (e.g. active LLM model)."""
    __tablename__ = "config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class ComplianceScore(Base):
    __tablename__ = "compliance_scores"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    rubric_name = Column(String(100), nullable=False)
    score = Column(Integer, nullable=False)
    criteria_json = Column(Text, nullable=False)
    scored_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_compliance_scores_doc", "document_id"),
    )


# ── Migration helpers ──────────────────────────────────────────────────────────

def _migrate_existing_tables():
    """Add new columns to existing tables without losing data (SQLite ALTER TABLE)."""
    new_columns = [
        # (table, column, sql_type)
        ("documents", "document_group_id",       "VARCHAR"),
        ("documents", "markdown_content",         "TEXT"),
        ("documents", "generation_time_seconds",  "REAL"),
        ("documents", "created_by_id",            "INTEGER"),
        ("documents", "export_format",            "VARCHAR DEFAULT 'docx'"),
        ("documents", "project_id",               "INTEGER"),
        ("snippets",  "tags",                     "VARCHAR"),
        ("snippets",  "project_id",               "INTEGER"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
            except Exception:
                pass  # column already exists — safe to skip


def create_tables():
    Base.metadata.create_all(bind=engine)
    _migrate_existing_tables()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
