from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from services.timezone_utils import format_ist_datetime

from models import Post, PostReaction, PostView, User
from schemas import PostOut, ReactionCreate, UnreadCountOut
from db import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.get("/", response_model=List[PostOut])
def get_posts(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all posts with reactions and view status"""
    
    # Get posts with author info
    posts_query = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.reactions),
        joinedload(Post.views)
    ).filter(Post.status == "published")
    
    # Order by pinned first, then by creation date desc
    posts = posts_query.order_by(
        Post.is_pinned.desc(), 
        Post.id.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for post in posts:
        # Count reactions by emoji
        reaction_counts = {}
        user_reactions = []
        
        for reaction in post.reactions:
            if reaction.emoji not in reaction_counts:
                reaction_counts[reaction.emoji] = 0
            reaction_counts[reaction.emoji] += 1
            
            if reaction.user_id == current_user.id:
                user_reactions.append(reaction.emoji)
        
        # Check if user has viewed this post
        is_viewed = any(view.user_id == current_user.id for view in post.views)
        
        post_data = PostOut(
            id=post.id,
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            author_name=post.author.username if post.author else None,
            created_at=format_ist_datetime(post.created_at),  # Convert to IST string
            updated_at=format_ist_datetime(post.updated_at),
            is_pinned=post.is_pinned,
            status=post.status,
            reaction_counts=reaction_counts,
            user_reactions=user_reactions,
            is_viewed=is_viewed
        )
        result.append(post_data)
    
    return result

@router.post("/{post_id}/react")
def toggle_reaction(
    post_id: int,
    reaction: ReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add or remove a reaction"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if reaction already exists
    existing_reaction = db.query(PostReaction).filter(
        PostReaction.post_id == post_id,
        PostReaction.user_id == current_user.id,
        PostReaction.emoji == reaction.emoji
    ).first()
    
    if existing_reaction:
        # Remove reaction
        db.delete(existing_reaction)
        action = "removed"
    else:
        # Add reaction
        new_reaction = PostReaction(
            post_id=post_id,
            user_id=current_user.id,
            emoji=reaction.emoji
        )
        db.add(new_reaction)
        action = "added"
    
    db.commit()
    return {"message": f"Reaction {action}", "emoji": reaction.emoji}

@router.post("/{post_id}/view")
def mark_post_viewed(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark post as viewed"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if already viewed
    existing_view = db.query(PostView).filter(
        PostView.post_id == post_id,
        PostView.user_id == current_user.id
    ).first()
    
    if not existing_view:
        view = PostView(post_id=post_id, user_id=current_user.id)
        db.add(view)
        db.commit()
    
    return {"message": "Post marked as viewed"}

@router.get("/unread/count", response_model=UnreadCountOut)
def get_unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get count of unread posts"""
    
    # Get all published posts
    all_posts = db.query(Post.id).filter(Post.status == "published").all()
    all_post_ids = [p.id for p in all_posts]
    
    # Get viewed post IDs for current user
    viewed_posts = db.query(PostView.post_id).filter(
        PostView.user_id == current_user.id
    ).all()
    viewed_post_ids = [v.post_id for v in viewed_posts]
    
    # Calculate unread count
    unread_count = len([pid for pid in all_post_ids if pid not in viewed_post_ids])
    
    return UnreadCountOut(unread_count=unread_count)
