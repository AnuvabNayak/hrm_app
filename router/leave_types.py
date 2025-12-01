"""
Leave Types Router - CRUD for Leave Type Management
====================================================
Admin interface for managing leave type policies.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List

from models import LeaveType
from schemas import LeaveTypeCreate, LeaveTypeUpdate, LeaveTypeOut
from db import get_db
from dependencies import allow_admin
from datetime import datetime, timezone

router = APIRouter(prefix="/leave-types", tags=["Leave Types"])


# ============================================================================
# CREATE LEAVE TYPE
# ============================================================================

@router.post("", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(allow_admin)])
def create_leave_type(
    leave_type: LeaveTypeCreate,
    db: Session = Depends(get_db)
):
    """
    Create new leave type with policies.
    
    Admin only. Defines leave type with:
    - Quota allocation
    - Half-day support
    - Approval requirements
    - Balance usage
    - Notice period
    - Max days per request
    """
    # Check if code already exists
    existing = db.query(LeaveType).filter(LeaveType.code == leave_type.code).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Leave type with code '{leave_type.code}' already exists"
        )
    
    db_leave_type = LeaveType(
        code=leave_type.code,
        name=leave_type.name,
        description=leave_type.description,
        default_annual_quota=leave_type.default_annual_quota,
        allow_half_day=leave_type.allow_half_day,
        requires_approval=leave_type.requires_approval,
        uses_balance=leave_type.uses_balance,
        min_notice_days=leave_type.min_notice_days,
        max_days_per_request=leave_type.max_days_per_request,
        display_order=leave_type.display_order,
        is_active=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    db.add(db_leave_type)
    db.commit()
    db.refresh(db_leave_type)
    return db_leave_type


# ============================================================================
# GET LEAVE TYPES
# ============================================================================

@router.get("", response_model=List[LeaveTypeOut])
def get_leave_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get all leave types.
    
    Available to all authenticated users.
    By default, returns only active leave types.
    """
    query = db.query(LeaveType)
    
    if not include_inactive:
        query = query.filter(LeaveType.is_active == True)
    
    leave_types = query.order_by(LeaveType.display_order, LeaveType.name).all()
    return leave_types


@router.get("/{leave_type_id}", response_model=LeaveTypeOut)
def get_leave_type(
    leave_type_id: int = Path(...),
    db: Session = Depends(get_db)
):
    """Get specific leave type by ID."""
    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    return leave_type


# ============================================================================
# UPDATE LEAVE TYPE
# ============================================================================

@router.patch("/{leave_type_id}", response_model=LeaveTypeOut, dependencies=[Depends(allow_admin)])
def update_leave_type(
    leave_type_id: int = Path(...),
    updates: LeaveTypeUpdate = ...,
    db: Session = Depends(get_db)
):
    """
    Update leave type policies.
    
    Admin only. Can update:
    - Name, description
    - Quota, half-day support
    - Approval requirements
    - Notice periods, limits
    - Active status
    """
    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    
    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(leave_type, field, value)
    
    leave_type.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    db.refresh(leave_type)
    return leave_type


# ============================================================================
# DELETE LEAVE TYPE (SOFT DELETE)
# ============================================================================

@router.delete("/{leave_type_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
def delete_leave_type(
    leave_type_id: int = Path(...),
    db: Session = Depends(get_db)
):
    """
    Soft delete leave type (sets is_active to False).
    
    Admin only. Does not delete from database to preserve
    historical leave request references.
    """
    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    
    leave_type.is_active = False
    leave_type.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    return None


# ============================================================================
# ACTIVATE LEAVE TYPE
# ============================================================================

@router.post("/{leave_type_id}/activate", response_model=LeaveTypeOut, dependencies=[Depends(allow_admin)])
def activate_leave_type(
    leave_type_id: int = Path(...),
    db: Session = Depends(get_db)
):
    """
    Reactivate a deactivated leave type.
    
    Admin only.
    """
    leave_type = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave type not found")
    
    leave_type.is_active = True
    leave_type.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    db.refresh(leave_type)
    return leave_type
