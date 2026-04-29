"""
Analytics router — aggregated data for the dashboard.
Accessible to admin and approver roles only.
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from models.database import get_db, Document
from models.schemas import AnalyticsResponse, AnalyticsSummary
from services.auth_service import require_admin_or_approver

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Common English stop-words to exclude from keyword analysis
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "have", "from", "will",
    "been", "were", "they", "their", "what", "when", "where", "which",
    "there", "then", "than", "into", "some", "more", "also", "each",
    "only", "such", "both", "just", "should", "could", "would", "about",
    "after", "before", "during", "under", "over", "between", "through",
    "document", "section", "include", "based", "using", "used", "must",
    "need", "needs", "make", "made", "well", "like", "able",
}


@router.get("/data", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db), _=Depends(require_admin_or_approver)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Summary cards ──────────────────────────────────────────────────────────
    total_docs = db.query(func.count(Document.id)).scalar() or 0

    docs_this_week = (
        db.query(func.count(Document.id))
        .filter(Document.created_at >= week_ago)
        .scalar() or 0
    )

    avg_gen_time = (
        db.query(func.avg(Document.generation_time_seconds))
        .filter(Document.generation_time_seconds.isnot(None))
        .scalar()
    )

    top_type_row = (
        db.query(Document.doc_type, func.count(Document.id).label("cnt"))
        .group_by(Document.doc_type)
        .order_by(func.count(Document.id).desc())
        .first()
    )
    most_used_type = top_type_row[0] if top_type_row else None

    # ── Docs per day — last 30 days ────────────────────────────────────────────
    daily_rows = (
        db.query(
            func.strftime("%Y-%m-%d", Document.created_at).label("date"),
            func.count(Document.id).label("count"),
        )
        .filter(Document.created_at >= month_ago)
        .group_by(func.strftime("%Y-%m-%d", Document.created_at))
        .order_by(func.strftime("%Y-%m-%d", Document.created_at))
        .all()
    )
    docs_per_day = [{"date": r.date, "count": r.count} for r in daily_rows]

    # ── By type ────────────────────────────────────────────────────────────────
    by_type = [
        {"doc_type": r.doc_type, "count": r.cnt}
        for r in db.query(
            Document.doc_type,
            func.count(Document.id).label("cnt"),
        ).group_by(Document.doc_type).all()
    ]

    # ── By status ──────────────────────────────────────────────────────────────
    by_status = [
        {"status": r.status, "count": r.cnt}
        for r in db.query(
            Document.status,
            func.count(Document.id).label("cnt"),
        ).group_by(Document.status).all()
    ]

    # ── Top keywords (Python-side NLP) ─────────────────────────────────────────
    instructions_rows = db.query(Document.instructions).all()
    words: list[str] = []
    for (text,) in instructions_rows:
        words.extend(re.findall(r"\b[a-zA-Z]{4,}\b", (text or "").lower()))
    filtered = [w for w in words if w not in _STOPWORDS]
    top_keywords = [
        {"word": word, "count": cnt}
        for word, cnt in Counter(filtered).most_common(20)
    ]

    # ── Avg generation time per day ────────────────────────────────────────────
    time_rows = (
        db.query(
            func.strftime("%Y-%m-%d", Document.created_at).label("date"),
            func.avg(Document.generation_time_seconds).label("avg_seconds"),
        )
        .filter(
            Document.generation_time_seconds.isnot(None),
            Document.created_at >= month_ago,
        )
        .group_by(func.strftime("%Y-%m-%d", Document.created_at))
        .order_by(func.strftime("%Y-%m-%d", Document.created_at))
        .all()
    )
    avg_time_per_day = [
        {"date": r.date, "avg_seconds": round(r.avg_seconds or 0, 1)}
        for r in time_rows
    ]

    return AnalyticsResponse(
        summary=AnalyticsSummary(
            total_docs=total_docs,
            docs_this_week=docs_this_week,
            avg_generation_time=round(avg_gen_time, 1) if avg_gen_time else None,
            most_used_type=most_used_type,
        ),
        docs_per_day=docs_per_day,
        by_type=by_type,
        by_status=by_status,
        top_keywords=top_keywords,
        avg_time_per_day=avg_time_per_day,
    )
