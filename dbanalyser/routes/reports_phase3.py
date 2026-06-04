"""
Phase 3: Reports & Help System API Routes
Reports generation, scheduling, help articles, and knowledge base
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from io import BytesIO

from database import get_db
from services.reports_service import ReportsService
from services.help_service import HelpService
from schemas import (
    ReportTemplateCreate,
    ScheduledReportCreate,
    HelpArticleCreate,
    HelpArticleFeedback
)

router = APIRouter(prefix="/api/v1", tags=["phase3"])


# ============================================================================
# PHASE 3: Report Generation & Management Endpoints
# ============================================================================

@router.post("/reports/templates")
async def create_report_template(
    template: ReportTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new report template"""
    service = ReportsService(db)
    try:
        result = service.create_report_template(
            template_name=template.template_name,
            description=template.description,
            report_type=template.report_type,
            template_config=template.template_config
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/generate/pdf")
async def generate_pdf_report(
    template_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Generate PDF report"""
    service = ReportsService(db)
    try:
        findings = service.get_findings_for_report()
        buffer, count = service.generate_pdf_report(template_id, findings)

        return {
            "success": True,
            "format": "pdf",
            "rows": count,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/generate/excel")
async def generate_excel_report(
    template_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Generate Excel report"""
    service = ReportsService(db)
    try:
        findings = service.get_findings_for_report()
        buffer, count = service.generate_excel_report(template_id, findings)

        return {
            "success": True,
            "format": "excel",
            "rows": count,
            "file_size_kb": len(buffer.getvalue()) // 1024,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/schedule")
async def schedule_report(
    schedule: ScheduledReportCreate,
    db: Session = Depends(get_db)
):
    """Schedule a report with cron expression"""
    service = ReportsService(db)
    try:
        result = service.schedule_report(
            template_id=schedule.template_id,
            cron_expression=schedule.cron_expression,
            recipients=schedule.recipients,
            format_type=schedule.format_type
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reports/executions/{scheduled_report_id}")
async def get_report_executions(
    scheduled_report_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get execution history for a scheduled report"""
    service = ReportsService(db)
    try:
        history = service.get_report_execution_history(scheduled_report_id, limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reports/metrics")
async def get_report_metrics(
    report_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get aggregated metrics for reports"""
    service = ReportsService(db)
    try:
        metrics = service.calculate_report_metrics(report_date)
        return {"success": True, "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reports/trends")
async def get_finding_trends(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get finding trends over time"""
    service = ReportsService(db)
    try:
        trends = service.get_finding_trends(days)
        return {"success": True, "data": trends}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# PHASE 3: Help System & Knowledge Base Endpoints
# ============================================================================

@router.post("/help/articles")
async def create_help_article(
    article: HelpArticleCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Create a new help article"""
    service = HelpService(db)
    try:
        result = service.create_help_article(
            title=article.title,
            content=article.content,
            category=article.category,
            tags=article.tags,
            user_id=user_id,
            is_published=article.is_published
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/search")
async def search_help_articles(
    query: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search help articles"""
    service = HelpService(db)
    try:
        articles = service.search_articles(query, category, limit)
        return {"success": True, "data": articles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/articles/{slug}")
async def get_article_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get help article by slug"""
    service = HelpService(db)
    try:
        article = service.get_article_by_slug(slug)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"success": True, "data": article}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/help/articles/{article_id}/vote")
async def record_helpful_vote(
    article_id: int,
    is_helpful: bool = Query(...),
    db: Session = Depends(get_db)
):
    """Record helpful/not helpful vote"""
    service = HelpService(db)
    try:
        result = service.record_helpful_vote(article_id, is_helpful)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/help/articles/{article_id}/feedback")
async def submit_article_feedback(
    article_id: int,
    feedback: HelpArticleFeedback,
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Submit feedback on an article"""
    service = HelpService(db)
    try:
        result = service.submit_article_feedback(
            article_id=article_id,
            user_id=user_id,
            feedback_type=feedback.feedback_type,
            feedback_text=feedback.feedback_text
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/categories/{category}")
async def get_articles_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all articles in a category"""
    service = HelpService(db)
    try:
        articles = service.get_articles_by_category(category, limit)
        return {"success": True, "data": articles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/trending")
async def get_trending_articles(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get trending articles"""
    service = HelpService(db)
    try:
        articles = service.get_trending_articles(limit)
        return {"success": True, "data": articles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/popular")
async def get_popular_articles(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get popular articles by helpful votes"""
    service = HelpService(db)
    try:
        articles = service.get_popular_articles(limit)
        return {"success": True, "data": articles}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/help/articles/{article_id}/feedback")
async def get_article_feedback(
    article_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get feedback for an article"""
    service = HelpService(db)
    try:
        feedback = service.get_article_feedback(article_id, limit)
        return {"success": True, "data": feedback}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/help/articles/{article_id}")
async def update_help_article(
    article_id: int,
    title: Optional[str] = Query(None),
    content: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    is_published: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """Update a help article"""
    service = HelpService(db)
    try:
        result = service.update_article(
            article_id=article_id,
            title=title,
            content=content,
            category=category,
            tags=tags,
            is_published=is_published
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
