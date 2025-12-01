"""
Departments Router - Organizational Structure Management
=========================================================
Admin interface for managing departments and hierarchy.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from models import Department, Employee
from schemas import DepartmentCreate, DepartmentUpdate, DepartmentOut
from db import get_db
from dependencies import allow_admin, get_current_user
from datetime import datetime, timezone

router = APIRouter(prefix="/departments", tags=["Departments"])


# ============================================================================
# CREATE DEPARTMENT
# ============================================================================

@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(allow_admin)])
def create_department(
    department: DepartmentCreate,
    db: Session = Depends(get_db)
):
    """
    Create new department.
    
    Admin only. Supports hierarchical structure with:
    - Parent department (for sub-departments)
    - Head of Department (HOD) assignment
    - Department code (unique identifier)
    """
    # Check if code already exists
    existing = db.query(Department).filter(Department.code == department.code).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Department with code '{department.code}' already exists"
        )
    
    # Validate parent department if specified
    if department.parent_department_id:
        parent = db.query(Department).filter(
            Department.id == department.parent_department_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent department not found")
    
    # Validate HOD if specified
    if department.hod_employee_id:
        hod = db.query(Employee).filter(
            Employee.id == department.hod_employee_id
        ).first()
        if not hod:
            raise HTTPException(status_code=404, detail="HOD employee not found")
    
    db_department = Department(
        name=department.name,
        code=department.code,
        description=department.description,
        parent_department_id=department.parent_department_id,
        hod_employee_id=department.hod_employee_id,
        is_active=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department


# ============================================================================
# GET DEPARTMENTS
# ============================================================================

@router.get("", response_model=List[DepartmentOut])
def get_departments(
    include_inactive: bool = False,
    parent_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get all departments.
    
    Available to all authenticated users.
    
    Query params:
    - include_inactive: Show deactivated departments
    - parent_id: Filter by parent department (use null for root departments)
    """
    query = db.query(Department)
    
    if not include_inactive:
        query = query.filter(Department.is_active == True)
    
    if parent_id is not None:
        query = query.filter(Department.parent_department_id == parent_id)
    
    departments = query.order_by(Department.name).all()
    return departments


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int = Path(...),
    db: Session = Depends(get_db)
):
    """Get specific department by ID."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


# ============================================================================
# UPDATE DEPARTMENT
# ============================================================================

@router.patch("/{department_id}", response_model=DepartmentOut, dependencies=[Depends(allow_admin)])
def update_department(
    department_id: int = Path(...),
    updates: DepartmentUpdate = ...,
    db: Session = Depends(get_db)
):
    """
    Update department information.
    
    Admin only. Can update:
    - Name, description
    - Parent department (change hierarchy)
    - HOD assignment
    - Active status
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Validate parent department if being updated
    if updates.parent_department_id is not None:
        # Prevent circular reference
        if updates.parent_department_id == department_id:
            raise HTTPException(
                status_code=400,
                detail="Department cannot be its own parent"
            )
        
        parent = db.query(Department).filter(
            Department.id == updates.parent_department_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent department not found")
    
    # Validate HOD if being updated
    if updates.hod_employee_id is not None:
        hod = db.query(Employee).filter(
            Employee.id == updates.hod_employee_id
        ).first()
        if not hod:
            raise HTTPException(status_code=404, detail="HOD employee not found")
    
    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)
    
    department.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    db.refresh(department)
    return department


# ============================================================================
# DELETE DEPARTMENT (SOFT DELETE)
# ============================================================================

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
def delete_department(
    department_id: int = Path(...),
    db: Session = Depends(get_db)
):
    """
    Soft delete department (sets is_active to False).
    
    Admin only. Does not delete from database to preserve
    employee department history.
    
    Note: Employees in this department will still reference it.
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check if department has active employees
    active_employees = db.query(Employee).filter(
        Employee.department_id == department_id,
        Employee.is_active == True
    ).count()
    
    if active_employees > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot deactivate department with {active_employees} active employees. Reassign them first."
        )
    
    department.is_active = False
    department.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    return None


# ============================================================================
# GET DEPARTMENT EMPLOYEES
# ============================================================================

@router.get("/{department_id}/employees", response_model=List[dict])
def get_department_employees(
    department_id: int = Path(...),
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get all employees in a department.
    
    Returns basic employee information.
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    query = db.query(Employee).filter(Employee.department_id == department_id)
    
    if not include_inactive:
        query = query.filter(Employee.is_active == True)
    
    employees = query.all()
    
    return [
        {
            "id": emp.id,
            "name": emp.name,
            "email": emp.email,
            "emp_code": emp.emp_code,
            "is_manager": emp.is_manager,
            "employment_type": emp.employment_type
        }
        for emp in employees
    ]
