from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from services.timezone_utils import format_ist_datetime
from models import Post, PostReaction, PostView, User
from schemas import PostOut, ReactionCreate, UnreadCountOut, PostCreate, PostUpdate
from db import get_db
from dependencies import get_current_user, allow_admin
from services.notification_service import notify_post_created_email

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
            # ✅ ENSURE PROPER EMOJI HANDLING
            emoji = reaction.emoji if reaction.emoji else "👍"  # Fallback
            if emoji not in reaction_counts:
                reaction_counts[emoji] = 0
            reaction_counts[emoji] += 1
            
            if reaction.user_id == current_user.id:
                user_reactions.append(emoji)
        
        # Check if user has viewed this post
        is_viewed = any(view.user_id == current_user.id for view in post.views)
        
        # ✅ ENSURE CONTENT IS PROPERLY ENCODED
        post_content = post.content or ""
        post_title = post.title or ""
        
        post_data = PostOut(
            id=post.id,
            title=post_title,
            content=post_content,
            author_id=post.author_id,
            author_name=post.author.username if post.author else None,
            created_at=format_ist_datetime(post.created_at),
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
    
    # ✅ ENSURE EMOJI IS PROPERLY HANDLED
    emoji = reaction.emoji.strip() if reaction.emoji else "👍"
    
    # Check if reaction already exists
    existing_reaction = db.query(PostReaction).filter(
        PostReaction.post_id == post_id,
        PostReaction.user_id == current_user.id,
        PostReaction.emoji == emoji
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
            emoji=emoji
        )
        db.add(new_reaction)
        action = "added"
    
    db.commit()
    return {"message": f"Reaction {action}", "emoji": emoji}

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

@router.post("/admin/posts", response_model=PostOut, dependencies=[Depends(allow_admin)], tags=["Admin - Posts"])
def create_post(
    post: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new post (Admin only).
    
    - **title**: Post title
    - **content**: Post content (markdown supported)
    - **is_pinned**: Whether post should be pinned (optional, default: false)
    """
    try:
        # Create post in database
        db_post = Post(
            title=post.title,
            content=post.content,
            author_id=current_user.id,
            status="published",
            is_pinned=post.is_pinned if hasattr(post, 'is_pinned') else False
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        
        # Send email notification to all employees
        notify_post_created_email(db, db_post)
        
        return db_post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {str(e)}"
        )

@router.put("/admin/posts/{post_id}/pin", response_model=PostOut, dependencies=[Depends(allow_admin)])
def pin_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pin or unpin a post (Admin only)."""
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Toggle pin status
        post.is_pinned = not post.is_pinned
        db.commit()
        db.refresh(post)
        
        # Optional: Send email notification if pinned
        # if post.is_pinned:
        #     notify_post_pinned_email(db, post)
        
        return post
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pin post: {str(e)}"
        )
