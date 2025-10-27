from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timezone

from services.timezone_utils import format_ist_datetime
from models import Post, PostReaction, PostView, User
from schemas import PostCreate, PostUpdate, PostOutAdmin, ReactionDetail
from db import get_db
from dependencies import get_current_user, allow_admin

router = APIRouter(prefix="/admin/posts", tags=["Admin Posts"])


@router.post("/", response_model=PostOutAdmin, dependencies=[Depends(allow_admin)])
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
    
    return PostOutAdmin(
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
        reactions=[],
        total_reactions=0,
        view_count=0
    )


@router.get("/", response_model=List[PostOutAdmin], dependencies=[Depends(allow_admin)])
def get_all_posts_admin(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all posts for admin management with detailed reactions"""
    
    
    posts = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.reactions).joinedload(PostReaction.user),
        joinedload(Post.views)
    ).order_by(
        Post.is_pinned.desc(),
        Post.id.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for post in posts:
        
        reaction_counts = {}
        reactions_detail = []
        
        for reaction in post.reactions:
            emoji = reaction.emoji if reaction.emoji else "👍"
            
            # Count reactions
            if emoji not in reaction_counts:
                reaction_counts[emoji] = 0
            reaction_counts[emoji] += 1
            
            
            reactions_detail.append(
                ReactionDetail(
                    user_id=reaction.user_id,
                    username=reaction.user.username if reaction.user else "Unknown",
                    emoji=emoji,
                    created_at=format_ist_datetime(reaction.created_at)
                )
            )
        
        # COUNT TOTAL VIEWS
        view_count = len(post.views)
        total_reactions = sum(reaction_counts.values())
        
        post_data = PostOutAdmin(
            id=post.id,
            title=post.title,
            content=post.content,
            author_id=post.author_id,
            author_name=post.author.username if post.author else None,
            created_at=format_ist_datetime(post.created_at),
            updated_at=format_ist_datetime(post.updated_at),
            is_pinned=post.is_pinned,
            status=post.status,
            reaction_counts=reaction_counts,
            reactions=reactions_detail,
            total_reactions=total_reactions,
            view_count=view_count
        )
        result.append(post_data)
    
    return result


@router.delete("/{post_id}", dependencies=[Depends(allow_admin)])
def delete_post_admin(
    post_id: int,
    db: Session = Depends(get_db)
):
    """Delete a post (admin only)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db.delete(post)
    db.commit()
    return {"message": "Post deleted successfully"}


@router.post("/{post_id}/toggle-pin", dependencies=[Depends(allow_admin)])
def toggle_pin_admin(
    post_id: int,
    db: Session = Depends(get_db)
):
    """Toggle pin status of a post (admin only)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post.is_pinned = not post.is_pinned
    db.commit()
    db.refresh(post)
    
    return {
        "message": "Pin toggled",
        "is_pinned": post.is_pinned
    }
