from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db import get_db
from dependencies import get_current_user
from services.quotes import get_today_quote, get_quote_history

router = APIRouter(prefix="/inspiration", tags=["Inspiration"])

@router.get("/today")
def quote_today(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Get today's inspirational quote"""
    return get_today_quote(db)

@router.get("/history")
def quote_history(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    """Get quote history for last N days"""
    return get_quote_history(db, days)

@router.post("/refresh-today")
def refresh_today_quote(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Manually refresh today's quote (admin feature)"""
    from services.quotes import fetch_and_store_quote
    
    try:
        fetch_and_store_quote(db)
        return {"message": "Quote refreshed successfully"}
    except Exception as e:
        return {"error": f"Failed to refresh quote: {str(e)}"}
