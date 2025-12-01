from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from models import Role, User
from schemas import RoleOut, RoleCreate, RoleUpdate
from db import get_db
from dependencies import allow_super_admin, get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.get("/", response_model=List[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive roles"),
    current_user = Depends(get_current_user)
):
    """
    List all available roles.
    
    - **include_inactive**: Include inactive roles in the response (default: False)
    
    Returns list of roles ordered by hierarchy level (employee → admin → super_admin).
    """
    query = db.query(Role)
    if not include_inactive:
        query = query.filter(Role.is_active == True)
    
    roles = query.order_by(Role.level).all()
    return roles

@router.get("/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get specific role details by ID.
    
    - **role_id**: Unique role identifier
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.post("/", response_model=RoleOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(allow_super_admin)])
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db)
):
    """
    Create new custom role (super admin only).
    
    System roles (employee, admin, super_admin) are predefined.
    This endpoint is for creating additional custom roles like "manager", "hr", etc.
    
    - **name**: Unique role identifier (lowercase, alphanumeric with underscores)
    - **display_name**: Human-readable name
    - **description**: Role description (optional)
    - **level**: Hierarchy level (0-100, higher = more permissions)
    - **is_active**: Whether role is active (default: True)
    """
    # Check if role name already exists
    existing = db.query(Role).filter(Role.name == role.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{role.name}' already exists"
        )
    
    # Create role
    db_role = Role(**role.model_dump())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    return db_role

@router.put("/{role_id}", response_model=RoleOut, dependencies=[Depends(allow_super_admin)])
def update_role(
    role_id: int,
    role_update: RoleUpdate,
    db: Session = Depends(get_db)
):
    """
    Update existing role (super admin only).
    
    **Note:** System roles (id 1, 2, 3) cannot be modified to maintain system integrity.
    
    - **role_id**: Role ID to update
    """
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent updating system roles
    if db_role.id <= 3:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot modify system role '{db_role.name}'. System roles are protected."
        )
    
    # Update only provided fields
    update_data = role_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_role, field, value)
    
    db.commit()
    db.refresh(db_role)
    
    return db_role

@router.delete("/{role_id}", dependencies=[Depends(allow_super_admin)])
def delete_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete custom role (super admin only).
    
    **Restrictions:**
    - System roles (id 1, 2, 3) cannot be deleted
    - Cannot delete role if users are assigned to it
    
    - **role_id**: Role ID to delete
    """
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent deleting system roles
    if db_role.id <= 3:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete system role '{db_role.name}'. System roles are protected."
        )
    
    # Check if any users have this role
    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{db_role.name}'. {user_count} user(s) are assigned to this role. Reassign users first."
        )
    
    db.delete(db_role)
    db.commit()
    
    return {
        "message": f"Role '{db_role.name}' deleted successfully",
        "deleted_id": role_id,
        "deleted_name": db_role.name
    }
