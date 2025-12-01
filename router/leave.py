"""
Leave Router - Hybrid Leave Policy
===================================
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from models import LeaveRequest, Employee, User
from schemas import (
    LeaveRequestCreate, 
    LeaveRequestOut, 
    LeaveApprovalRequest,
)
from db import get_db
from dependencies import get_current_user, allow_admin
from utils import ensure_utc_naive

from services.leave_service import (
    create_leave_request,
    approve_leave_level,
    admin_approve_leave,
    deny_leave_request
)
from services.notification_service import (
    notify_leave_requested,
    notify_approval_pending,
    notify_leave_approved,
    notify_leave_denied,
    notify_leave_requested_email,
    notify_leave_approved_email,
    notify_leave_denied_email
)


router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.post("", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def request_leave(
    leave: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create leave request with automatic paid/unpaid calculation.
    
    System automatically splits request into paid/unpaid based on balance.
    Coins NOT consumed until admin approval.
    """
    # Determine employee_id
    if current_user.role not in ["admin", "super_admin"]:
        emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")
        employee_id = emp.id
    else:
        if leave.employee_id is None:
            raise HTTPException(
                status_code=400,
                detail="employee_id required for admin users"
            )
        employee_id = leave.employee_id
        
        emp = db.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
    
    start_utc = ensure_utc_naive(leave.start_date)
    end_utc = ensure_utc_naive(leave.end_date)
    half_day_utc = ensure_utc_naive(leave.half_day_date) if leave.half_day_date else None
    
    try:
        db_leave = create_leave_request(
            db=db,
            employee_id=employee_id,
            start_date=start_utc,
            end_date=end_utc,
            leave_type=leave.leave_type,
            reason=leave.reason,
            duration_type=leave.duration_type,
            half_day_date=half_day_utc,
            leave_type_id=leave.leave_type_id
        )
        
        notify_leave_requested(db, db_leave, current_user.id)
        
        # Notify approver if workflow initialized
        if db_leave.current_approver_id:
            approver_emp = db.query(Employee).filter(
                Employee.id == db_leave.current_approver_id
            ).first()
            if approver_emp:
                notify_approval_pending(db, db_leave, approver_emp.user_id)
        
        
        return db_leave
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{leave_id}/review", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
def review_leave(
    leave_id: int = Path(...),
    review: LeaveApprovalRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approve or deny leave request (Admin only).
    
    Approval: Consumes coins for paid days, marks unpaid for payroll.
    Denial: No coins consumed.
    """
    try:
        if review.action == "approve":
            db_leave = admin_approve_leave(
                db=db,
                leave_request_id=leave_id,
                approved_by_user_id=current_user.id,
                admin_notes=review.admin_notes
            )
            if requester_emp:
                notify_leave_approved_email(db, db_leave, requester_emp.user_id)
        else:
            db_leave = deny_leave_request(
                db=db,
                leave_request_id=leave_id,
                denied_by_user_id=current_user.id,
                admin_notes=review.admin_notes
            )
            if requester_emp:
                notify_leave_denied_email(db, db_leave, requester_emp.user_id, review.admin_notes)
        
        requester_emp = db.query(Employee).filter(
            Employee.id == db_leave.employee_id
        ).first()
        
        if requester_emp:
            if db_leave.status == "approved":
                notify_leave_approved(db, db_leave, requester_emp.user_id)
            else:
                notify_leave_denied(db, db_leave, requester_emp.user_id, review.admin_notes)
        
        return db_leave
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{leave_id}/approve-level", response_model=LeaveRequestOut)
def approve_at_level(
    leave_id: int = Path(...),
    review: LeaveApprovalRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manager approves/denies leave at their workflow level.
    
    Features:
    - Workflow-aware approval
    - Advances to next approver if exists
    - Consumes coins only when fully approved
    - Notifications to requester and next approver
    """
    approve = (review.action == "approve")
    
    try:
        db_leave = approve_leave_level(
            db=db,
            leave_request_id=leave_id,
            actor_user=current_user,
            approve=approve,
            comments=review.admin_notes
        )
        
        # Get requester employee
        requester_emp = db.query(Employee).filter(
            Employee.id == db_leave.employee_id
        ).first()
        
        # Notify requester
        if requester_emp:
            if db_leave.status == "approved":
                notify_leave_approved(db, db_leave, requester_emp.user_id)
            elif db_leave.status == "denied":
                notify_leave_denied(db, db_leave, requester_emp.user_id, review.admin_notes)
        
        # Notify next approver if advanced to next level
        if db_leave.current_approver_id and db_leave.status == "pending":
            next_approver_emp = db.query(Employee).filter(
                Employee.id == db_leave.current_approver_id
            ).first()
            if next_approver_emp:
                notify_approval_pending(db, db_leave, next_approver_emp.user_id)
        
        return db_leave
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending-approval", response_model=List[LeaveRequestOut])
def get_pending_approvals(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get leave requests pending current user's approval.
    
    Shows requests where user is current_approver_id
    """
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    requests = db.query(LeaveRequest)\
        .filter(
            LeaveRequest.current_approver_id == emp.id,
            LeaveRequest.status == "pending"
        )\
        .order_by(LeaveRequest.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return requests


@router.get("/me", response_model=List[LeaveRequestOut])
def get_my_leave_requests(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get leave requests for current user."""
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    requests = db.query(LeaveRequest)\
        .filter(LeaveRequest.employee_id == emp.id)\
        .order_by(LeaveRequest.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return requests


@router.get("", response_model=List[LeaveRequestOut], dependencies=[Depends(allow_admin)])
def get_all_leave_requests(
    skip: int = 0,
    limit: int = 10,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all leave requests (Admin only)."""
    query = db.query(LeaveRequest)
    
    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)
    
    requests = query\
        .order_by(LeaveRequest.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return requests


@router.get("/{leave_id}", response_model=LeaveRequestOut)
def get_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific leave request."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if current_user.role not in ["admin", "super_admin"]:
        employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
        
        # Check authorization: Must be the employee or the current approver
        if not employee or employee.user_id != current_user.id:
            approver_emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
            if not approver_emp or leave.current_approver_id != approver_emp.id:
                raise HTTPException(status_code=403, detail="Not authorized")
    
    return leave


# Old code for reference (to be removed)



# from fastapi import APIRouter, Depends, HTTPException, status, Path
# from sqlalchemy.orm import Session
# from models import LeaveRequest, Employee
# from schemas import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestOut
# from db import get_db
# from dependencies import get_current_user, allow_admin
# from typing import List
# from utils import ensure_utc_naive

# router = APIRouter(prefix="/leaves", tags=["Leaves"])

# @router.post("/", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
# def create_leave(leave: LeaveRequestCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     # Auto-assign employee_id for regular employees
#     if current_user.role not in ["admin", "super_admin"]:
#         emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
#         if not emp:
#             raise HTTPException(status_code=404, detail="Employee profile not found")
#         leave.employee_id = emp.id
#     elif leave.employee_id is None:
#         # Admin must provide employee_id
#         raise HTTPException(status_code=400, detail="employee_id required for admin users")

#     # Validate employee exists and user has permission
#     employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
#     if not employee:
#         raise HTTPException(status_code=404, detail="Employee not found")
    
#     # Non-admin users can only create requests for themselves
#     if current_user.role not in ["admin", "super_admin"] and employee.user_id != current_user.id:
#         raise HTTPException(status_code=403, detail="Not authorized")

#     # Convert to UTC naive datetimes
#     start_utc = ensure_utc_naive(leave.start_date)
#     end_utc = ensure_utc_naive(leave.end_date)

#     # Validate dates
#     if end_utc < start_utc:
#         raise HTTPException(status_code=400, detail="End date must be >= start date")

#     # Check leave balance (only for employees, not admin-created requests)
#     if current_user.role not in ["admin", "super_admin"]:
#         from services.leave_coins import get_available_coins
        
#         # ✅ FIXED: Calculate duration directly (no missing function import)
#         duration = (end_utc.date() - start_utc.date()).days + 1
        
#         balance = get_available_coins(db, leave.employee_id)
        
#         if balance["available_coins"] < duration:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"Insufficient leave balance. Required: {duration}, Available: {balance['available_coins']}"
#             )

#     # Create leave request
#     db_leave = LeaveRequest(
#         employee_id=leave.employee_id,
#         start_date=start_utc,
#         end_date=end_utc,
#         leave_type=leave.leave_type,
#         reason=leave.reason,
#         status="pending"
#     )
    
#     db.add(db_leave)
#     db.commit()
#     db.refresh(db_leave)
    
#     return db_leave

# @router.post("/{leave_id}/approve", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
# def approve_leave(leave_id: int = Path(...), db: Session = Depends(get_db)):
#     from services.leave_coins import consume_coins

#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
#     if not leave:
#         raise HTTPException(status_code=404, detail="Leave request not found")

#     if leave.status == "approved":
#         raise HTTPException(status_code=400, detail="Leave already approved")

#     # Validate dates
#     if leave.end_date < leave.start_date:
#         raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

#     # Calculate days (inclusive)
#     start_date = leave.start_date.date()
#     end_date = leave.end_date.date()
#     days = (end_date - start_date).days + 1
#     if days <= 0:
#         raise HTTPException(status_code=400, detail="Invalid leave duration")

#     # Attempt to consume coins
#     consumed = consume_coins(db, leave.employee_id, amount=days, ref_leave_request_id=leave.id)
#     if consumed < days:
#         db.rollback()
#         raise HTTPException(status_code=400, detail="Insufficient leave balance")

#     # Set approved
#     leave.status = "approved"
#     db.commit()
#     db.refresh(leave)

#     return leave

# @router.post("/{leave_id}/deny", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
# def deny_leave(leave_id: int = Path(...), db: Session = Depends(get_db)):
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
#     if not leave:
#         raise HTTPException(status_code=404, detail="Leave request not found")
#     if leave.status == "denied":
#         raise HTTPException(status_code=400, detail="Leave already denied")
#     leave.status = "denied"
#     db.commit()
#     db.refresh(leave)
#     return leave

# @router.get("/", response_model=List[LeaveRequestOut])
# def read_leaves(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     query = db.query(LeaveRequest)
    
#     if current_user.role not in ["admin", "super_admin"]:
#         query = query.join(Employee).filter(Employee.user_id == current_user.id)
    
#     # ✅ ADD ORDER BY clause for MSSQL compatibility
#     return query.order_by(LeaveRequest.id.desc()).offset(skip).limit(limit).all()

# @router.get("/{leave_id}", response_model=LeaveRequestOut)
# def read_leave(leave_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
#     if not leave:
#         raise HTTPException(status_code=404, detail="Leave request not found")
#     employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
#     if current_user.role not in ["admin", "super_admin"] and (not employee or employee.user_id != current_user.id):
#         raise HTTPException(status_code=403, detail="Operation not permitted")
#     return leave

# @router.put("/{leave_id}", response_model=LeaveRequestOut)
# def update_leave(leave_id: int, update: LeaveRequestUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
#     if not leave:
#         raise HTTPException(status_code=404, detail="Leave request not found")
#     # Employees cannot update leave once submitted; only admins can modify
#     if current_user.role not in ["admin", "super_admin"]:
#         raise HTTPException(status_code=403, detail="Employees cannot update leave once submitted")

#     for field, value in update.model_dump(exclude_unset=True).items():
#         setattr(leave, field, value)
#     db.commit()
#     db.refresh(leave)
#     return leave

# @router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
# def delete_leave(leave_id: int, db: Session = Depends(get_db)):
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
#     if not leave:
#         raise HTTPException(status_code=404, detail="Leave request not found")
#     db.delete(leave)
#     db.commit()

