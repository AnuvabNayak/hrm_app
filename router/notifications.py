"""
Notifications Router - In-App Notification Management
======================================================
User interface for managing in-app notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List

from models import Notification, User
from schemas import NotificationOut
from db import get_db
from dependencies import get_current_user
from services.notification_service import mark_as_read, mark_all_as_read

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================================================
# GET NOTIFICATIONS
# ============================================================================

@router.get("", response_model=List[NotificationOut])
def get_notifications(
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get notifications for current user.
    
    Query params:
    - skip: Pagination offset
    - limit: Max results (default 20)
    - unread_only: Show only unread notifications
    """
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    notifications = query\
        .order_by(Notification.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return notifications


@router.get("/unread-count", response_model=dict)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get count of unread notifications.
    
    Returns:
        {"count": 5}
    """
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    
    return {"count": count}


# ============================================================================
# MARK AS READ
# ============================================================================

@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark specific notification as read."""
    success = mark_as_read(db, notification_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    return notification


@router.post("/mark-all-read", response_model=dict)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all notifications as read for current user.
    
    Returns:
        {"marked_count": 12}
    """
    count = mark_all_as_read(db, current_user.id)
    return {"marked_count": count}


# ============================================================================
# DELETE NOTIFICATION
# ============================================================================

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete specific notification.
    
    Users can only delete their own notifications.
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    return None


@router.delete("/clear-all", status_code=status.HTTP_204_NO_CONTENT)
def clear_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all notifications for current user.
    
    Use with caution - this is permanent.
    """
    db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).delete()
    
    db.commit()
    return None
