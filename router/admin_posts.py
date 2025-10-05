from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from services.timezone_utils import format_ist_datetime

from models import Post, User
from schemas import PostCreate, PostUpdate, PostOut
from db import get_db
from dependencies import get_current_user, allow_admin

router = APIRouter(prefix="/admin/posts", tags=["Admin Posts"])

@router.post("/", response_model=PostOut, dependencies=[Depends(allow_admin)])
def create_post(
    post: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new post (admin only)"""
    
    db_post = Post(
        title=post.title,
        content=post.content,
        author_id=current_user.id,
        is_pinned=post.is_pinned or False
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    return PostOut(
        id=db_post.id,
        title=db_post.title,
        content=db_post.content,
        author_id=db_post.author_id,
        author_name=current_user.username,
        created_at=format_ist_datetime(db_post.created_at),
        updated_at=format_ist_datetime(db_post.updated_at),
        is_pinned=db_post.is_pinned,
        status=db_post.status,
        reaction_counts={},
        user_reactions=[],
        is_viewed=False
    )

@router.get("/", response_model=List[PostOut], dependencies=[Depends(allow_admin)])
def get_all_posts_admin(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all posts for admin management"""
    
    posts = db.query(Post).order_by(
        Post.is_pinned.desc(),
        Post.id.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for post in posts:
        # Get author info
        author = db.query(User).filter(User.id == post.author_id).first()
        
        post_data = PostOut(
            id=post.id,
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            author_name=author.username if author else None,
            created_at=format_ist_datetime(post.created_at),
            updated_at=format_ist_datetime(post.updated_at),
            is_pinned=post.is_pinned,
            status=post.status,
            reaction_counts={},
            user_reactions=[],
            is_viewed=False
        )
        result.append(post_data)
    
    return result

@router.delete("/{post_id}", dependencies=[Depends(allow_admin)])
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """Delete post (admin only)"""
    
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db.delete(db_post)
    db.commit()
    
    return {"message": "Post deleted successfully"}

@router.post("/{post_id}/toggle-pin", dependencies=[Depends(allow_admin)])
def toggle_pin_post(post_id: int, db: Session = Depends(get_db)):
    """Toggle pin status of post"""
    
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db_post.is_pinned = not db_post.is_pinned
    db_post.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": f"Post {'pinned' if db_post.is_pinned else 'unpinned'}", "is_pinned": db_post.is_pinned}
