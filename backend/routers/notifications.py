from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from models.database import get_db, Notification
from models.schemas import NotificationRecord
from services.auth_service import get_current_user_optional

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=List[NotificationRecord])
def get_notifications(db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    count = db.query(Notification).filter(Notification.read == False).count()  # noqa: E712
    return {"count": count}


@router.patch("/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.read = True
        db.commit()
    return {"ok": True}


@router.patch("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), _=Depends(get_current_user_optional)):
    db.query(Notification).filter(Notification.read == False).update({"read": True})  # noqa: E712
    db.commit()
    return {"ok": True}
