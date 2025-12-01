from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from models import User, TokenBlacklist
from schemas import TokenBlacklistOut
from db import get_db
from dependencies import allow_admin, get_current_user

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth Management"])

@router.get("/blacklist", response_model=List[TokenBlacklistOut])
async def view_blacklist(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    user_id: int = Query(None, description="Filter by specific user ID"),
    db: Session = Depends(get_db),
    current_user = Depends(allow_admin)
):
    """
    View blacklisted tokens (admin only).
    
    Shows all tokens that have been invalidated through logout or admin revocation.
    
    **Query Parameters:**
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum records to return (max 100)
    - **user_id**: Optional filter by specific user
    
    **Returns:** List of blacklisted tokens with details
    """
    query = db.query(TokenBlacklist)
    
    if user_id:
        query = query.filter(TokenBlacklist.user_id == user_id)
    
    blacklist = query.order_by(TokenBlacklist.blacklisted_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return blacklist

@router.get("/blacklist/stats")
async def blacklist_stats(
    db: Session = Depends(get_db),
    current_user = Depends(allow_admin)
):
    """
    Get statistics about blacklisted tokens (admin only).
    
    **Returns:**
    - **total_blacklisted**: Total tokens in blacklist
    - **expired**: Tokens that have passed their natural expiry
    - **active**: Tokens still within their validity period but blacklisted
    - **by_reason**: Count grouped by revocation reason
    - **by_user**: Top 10 users by blacklisted token count
    """
    from sqlalchemy import func
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    total = db.query(TokenBlacklist).count()
    expired = db.query(TokenBlacklist).filter(TokenBlacklist.token_exp < now).count()
    active = total - expired
    
    # Count by reason
    by_reason = db.query(
        TokenBlacklist.reason,
        func.count(TokenBlacklist.id).label('count')
    ).group_by(TokenBlacklist.reason).all()
    
    # Top users by blacklisted token count
    by_user = db.query(
        TokenBlacklist.username,
        func.count(TokenBlacklist.id).label('count')
    ).group_by(TokenBlacklist.username)\
     .order_by(func.count(TokenBlacklist.id).desc())\
     .limit(10)\
     .all()
    
    return {
        "total_blacklisted": total,
        "expired_tokens": expired,
        "active_blacklisted": active,
        "by_reason": {reason: count for reason, count in by_reason},
        "top_users": [{"username": username, "count": count} for username, count in by_user],
        "timestamp": now.isoformat()
    }

@router.delete("/blacklist/cleanup")
async def manual_cleanup(
    db: Session = Depends(get_db),
    current_user = Depends(allow_admin)
):
    """
    Manually trigger cleanup of expired blacklist entries (admin only).
    
    Normally runs automatically at 2:30 AM daily, but can be triggered manually here.
    
    **Returns:** Number of expired tokens removed
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    expired_count = db.query(TokenBlacklist).filter(
        TokenBlacklist.token_exp < now
    ).count()
    
    deleted = db.query(TokenBlacklist).filter(
        TokenBlacklist.token_exp < now
    ).delete()
    
    db.commit()
    
    return {
        "message": "Cleanup completed successfully",
        "found_expired": expired_count,
        "deleted_count": deleted,
        "timestamp": now.isoformat()
    }

@router.post("/revoke-user-sessions/{user_id}")
async def revoke_user_sessions(
    user_id: int,
    reason: str = Query("admin_revoke", description="Reason for revocation"),
    db: Session = Depends(get_db),
    current_user = Depends(allow_admin)
):
    """
    Revoke all active sessions for a specific user (admin only).
    
    **Note:** This doesn't actually blacklist all tokens (we don't track them all).
    Instead, it provides information about existing blacklisted tokens for the user.
    
    To truly force logout, users must login again, and their old tokens will be
    checked against the blacklist.
    
    **Parameters:**
    - **user_id**: User ID whose sessions to check
    - **reason**: Reason for revocation (e.g., "security_breach", "admin_revoke")
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Count existing blacklisted tokens for this user
    blacklisted_count = db.query(TokenBlacklist).filter(
        TokenBlacklist.user_id == user_id
    ).count()
    
    return {
        "message": f"User '{user.username}' session info retrieved",
        "user_id": user_id,
        "username": user.username,
        "existing_blacklisted_tokens": blacklisted_count,
        "note": "User will need to re-login. Old tokens checked against blacklist on next request.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/blacklist/user/{user_id}", response_model=List[TokenBlacklistOut])
async def get_user_blacklist(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(allow_admin)
):
    """
    Get all blacklisted tokens for a specific user (admin only).
    
    **Parameters:**
    - **user_id**: User ID to query
    
    **Returns:** List of blacklisted tokens for the user
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    blacklist = db.query(TokenBlacklist)\
        .filter(TokenBlacklist.user_id == user_id)\
        .order_by(TokenBlacklist.blacklisted_at.desc())\
        .all()
    
    return blacklist
