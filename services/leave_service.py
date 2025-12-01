"""
Leave Service - Enhanced with Half-Day, Leave Types, and Workflow
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from typing import Tuple, Optional

from models import LeaveRequest, Employee, User, LeaveType, LeaveApproval
from services.leave_coins import get_available_coins, consume_coins


# HALF-DAY CALCULATION
# ============================================================================

def calculate_leave_days(
    start_date: datetime,
    end_date: datetime,
    duration_type: str = "full_day",
    half_day_date: Optional[datetime] = None
) -> Decimal:
    """
    Calculate leave days with half-day support.
    
    Returns:
        Decimal: Total days (e.g., 2.5 for 2 full + 1 half)
    """
    start = start_date.date() if hasattr(start_date, 'date') else start_date
    end = end_date.date() if hasattr(end_date, 'date') else end_date
    
    full_days = (end - start).days + 1
    
    if duration_type in ("first_half", "second_half"):
        if start == end:
            return Decimal("0.5")
        return Decimal(str(full_days - 0.5))
    
    return Decimal(str(full_days))


# PAID/UNPAID SPLIT
# ============================================================================

def calculate_paid_unpaid_split(
    db: Session,
    employee_id: int,
    total_days: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Calculate paid vs unpaid days.
    
    Returns:
        Tuple[Decimal, Decimal]: (paid_days, unpaid_days)
    """
    balance_info = get_available_coins(db, employee_id)
    available = Decimal(str(balance_info["available_coins"]))
    
    paid = min(total_days, available)
    unpaid = total_days - paid
    
    return (paid, unpaid)


# APPROVAL WORKFLOW HELPER
# ============================================================================

def determine_approval_workflow(db: Session, employee_id: int) -> list[dict]:
    """
    Determine approval steps for leave request.
    
    Returns:
        list: [{"level": 1, "level_name": "Manager", "approver_id": 123}]
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    steps = []
    
    if emp and emp.manager_id:
        steps.append({
            "level": 1,
            "level_name": "Manager",
            "approver_id": emp.manager_id
        })
    
    return steps


# CREATE LEAVE REQUEST
# ============================================================================

def create_leave_request(
    db: Session,
    employee_id: int,
    start_date: datetime,
    end_date: datetime,
    leave_type: str,
    reason: Optional[str] = None,
    duration_type: str = "full_day",
    half_day_date: Optional[datetime] = None,
    leave_type_id: Optional[int] = None
) -> LeaveRequest:
    """
    Create leave request with half-day support, LeaveType, and workflow.
    
    Args:
        db: Database session
        employee_id: Employee ID
        start_date: Leave start date
        end_date: Leave end date
        leave_type: Leave type name (for backward compatibility)
        reason: Leave reason
        duration_type: "full_day", "first_half", or "second_half"
        half_day_date: Date of half-day (required for half-day types)
        leave_type_id: Leave type ID (preferred)
    
    Returns:
        LeaveRequest: Created request with workflow initialized
    """
    if end_date < start_date:
        raise ValueError("End date must be >= start date")
    
    # Validate employee eligibility
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ValueError("Employee not found")
    if not emp.is_leave_eligible:
        raise ValueError("Employee not eligible for leave")
    
    # Find leave type
    lt = None
    if leave_type_id:
        lt = db.query(LeaveType).filter(
            LeaveType.id == leave_type_id,
            LeaveType.is_active == True
        ).first()
    
    if not lt:
        lt = db.query(LeaveType).filter(
            LeaveType.name == leave_type,
            LeaveType.is_active == True
        ).first()
    
    if not lt:
        # Fallback: create a default leave type if none exists
        lt = LeaveType(
            code="GENERAL",
            name=leave_type,
            description="Auto-generated leave type",
            default_annual_quota=0,
            allow_half_day=True,
            requires_approval=True,
            uses_balance=True,
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(lt)
        db.flush()
    
    # Validate half-day configuration
    if duration_type in ("first_half", "second_half"):
        if not lt.allow_half_day:
            raise ValueError("Half-day leave not allowed for this leave type")
        if not half_day_date:
            raise ValueError("half_day_date required for half-day leave")
    
    # Calculate days
    total_days = calculate_leave_days(start_date, end_date, duration_type, half_day_date)
    
    if total_days <= 0:
        raise ValueError("Invalid leave duration")
    
    # Calculate paid/unpaid split
    if lt.uses_balance:
        paid_days, unpaid_days = calculate_paid_unpaid_split(db, employee_id, total_days)
    else:
        paid_days = total_days
        unpaid_days = Decimal("0")
    
    # Create request
    leave_request = LeaveRequest(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        duration_type=duration_type,
        half_day_date=half_day_date.date() if half_day_date else None,
        total_days=total_days,
        paid_days=paid_days,
        unpaid_days=unpaid_days,
        leave_type=lt.name,
        leave_type_id=lt.id,
        reason=reason,
        status="pending",
        workflow_status="pending_manager",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(leave_request)
    db.flush()
    
    # Initialize approval workflow
    steps = determine_approval_workflow(db, employee_id)
    if steps:
        for i, step in enumerate(steps, start=1):
            approval = LeaveApproval(
                leave_request_id=leave_request.id,
                level=step["level"],
                level_name=step["level_name"],
                approver_id=step["approver_id"],
                status="pending",
                sequence=i,
                is_final=(i == len(steps)),
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(approval)
        
        leave_request.current_approver_id = steps[0]["approver_id"]
    else:
        leave_request.workflow_status = "pending_admin"
    
    db.commit()
    db.refresh(leave_request)
    return leave_request


# MANAGER/WORKFLOW APPROVAL
# ============================================================================

def approve_leave_level(
    db: Session,
    leave_request_id: int,
    actor_user: User,
    approve: bool,
    comments: Optional[str] = None
) -> LeaveRequest:
    """
    Manager approves/denies leave at their workflow level.
    
    Args:
        db: Database session
        leave_request_id: Leave request ID
        actor_user: User performing action (manager)
        approve: True to approve, False to deny
        comments: Optional comments
    
    Returns:
        LeaveRequest: Updated request
    """
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave:
        raise ValueError("Leave request not found")
    
    if leave.status != "pending":
        raise ValueError("Leave request is not pending")
    
    # Find approver employee
    approver_emp = db.query(Employee).filter(Employee.user_id == actor_user.id).first()
    if not approver_emp:
        raise PermissionError("Approver profile not found")
    
    # Find pending approval for this approver
    approval = db.query(LeaveApproval).filter(
        LeaveApproval.leave_request_id == leave_request_id,
        LeaveApproval.approver_id == approver_emp.id,
        LeaveApproval.status == "pending"
    ).order_by(LeaveApproval.sequence).first()
    
    if not approval:
        raise PermissionError("No pending approval for this user")
    
    # Update approval
    approval.status = "approved" if approve else "denied"
    approval.action_by_user_id = actor_user.id
    approval.action_at = datetime.now(timezone.utc).replace(tzinfo=None)
    approval.comments = comments
    
    if not approve:
        # Denied → End workflow
        leave.status = "denied"
        leave.workflow_status = "denied"
        leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(leave)
        return leave
    
    # Approved → Check for next level
    next_approval = db.query(LeaveApproval).filter(
        LeaveApproval.leave_request_id == leave_request_id,
        LeaveApproval.sequence > approval.sequence,
        LeaveApproval.status == "pending"
    ).order_by(LeaveApproval.sequence).first()
    
    if next_approval:
        # Advance to next level
        leave.current_approver_id = next_approval.approver_id
        leave.workflow_status = f"pending_level_{next_approval.level}"
    else:
        # Fully approved → Consume coins
        leave.status = "approved"
        leave.workflow_status = "fully_approved"
        leave.approved_by = actor_user.id
        leave.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if leave.paid_days and float(leave.paid_days) > 0:
            consumed = consume_coins(
                db,
                leave.employee_id,
                float(leave.paid_days),
                ref_leave_request_id=leave.id
            )
    
    leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(leave)
    return leave


# ADMIN APPROVAL (RENAMED FROM approve_leave_request)
# ============================================================================

def admin_approve_leave(
    db: Session,
    leave_request_id: int,
    approved_by_user_id: int,
    admin_notes: Optional[str] = None
) -> LeaveRequest:
    """
    Admin directly approves leave (bypass workflow).
    Kept for backward compatibility with admin UI.
    """
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave:
        raise ValueError("Leave request not found")
    
    if leave.status == "approved":
        raise ValueError("Leave already approved")
    
    if leave.status == "denied":
        raise ValueError("Cannot approve denied leave")
    
    # Skip all pending approvals
    db.query(LeaveApproval).filter(
        LeaveApproval.leave_request_id == leave_request_id,
        LeaveApproval.status == "pending"
    ).update({
        "status": "skipped",
        "action_by_user_id": approved_by_user_id,
        "action_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "comments": "Admin override"
    })
    
    # Recalculate in case balance changed
    current_paid, current_unpaid = calculate_paid_unpaid_split(
        db, leave.employee_id, leave.total_days
    )
    leave.paid_days = current_paid
    leave.unpaid_days = current_unpaid
    
    # Consume coins
    if leave.paid_days and float(leave.paid_days) > 0:
        consumed = consume_coins(
            db,
            leave.employee_id,
            float(leave.paid_days),
            ref_leave_request_id=leave.id
        )
        
        if consumed != float(leave.paid_days):
            db.rollback()
            raise ValueError(
                f"Insufficient balance. Required: {leave.paid_days}, Available: {consumed}"
            )
    
    leave.status = "approved"
    leave.workflow_status = "admin_approved"
    leave.approved_by = approved_by_user_id
    leave.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    leave.admin_notes = admin_notes
    leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    db.refresh(leave)
    return leave


# DENY LEAVE
# ============================================================================

def deny_leave_request(
    db: Session,
    leave_request_id: int,
    denied_by_user_id: int,
    admin_notes: Optional[str] = None
) -> LeaveRequest:
    """Deny leave request (no coins consumed)."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave:
        raise ValueError("Leave request not found")
    
    if leave.status == "denied":
        raise ValueError("Leave already denied")
    
    leave.status = "denied"
    leave.approved_by = denied_by_user_id
    leave.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    leave.admin_notes = admin_notes
    leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    db.commit()
    db.refresh(leave)
    return leave


# ============================================================================
# BACKWARD COMPATIBILITY ALIAS
# ============================================================================

# Keep old function name for existing code
approve_leave_request = admin_approve_leave


# """
# Leave Service - Hybrid Leave Policy
# ====================================
# Handles leave request creation with automatic paid/unpaid calculation.
# """

# from datetime import datetime, timezone
# from sqlalchemy.orm import Session
# from typing import Tuple, Optional

# from models import LeaveRequest, Employee, User
# from services.leave_coins import get_available_coins, consume_coins


# def calculate_leave_days(start_date: datetime, end_date: datetime) -> int:
#     """Calculate total leave days (inclusive)."""
#     start = start_date.date() if hasattr(start_date, 'date') else start_date
#     end = end_date.date() if hasattr(end_date, 'date') else end_date
#     return (end - start).days + 1


# def calculate_paid_unpaid_split(
#     db: Session,
#     employee_id: int,
#     total_days: int
# ) -> Tuple[int, int]:
#     """
#     Calculate paid vs unpaid days based on available balance.
    
#     Returns: (paid_days, unpaid_days)
#     """
#     balance_info = get_available_coins(db, employee_id)
#     available_coins = balance_info["available_coins"]
    
#     paid_days = min(total_days, available_coins)
#     unpaid_days = max(0, total_days - paid_days)
    
#     return paid_days, unpaid_days


# def create_leave_request(
#     db: Session,
#     employee_id: int,
#     start_date: datetime,
#     end_date: datetime,
#     leave_type: str,
#     reason: Optional[str] = None
# ) -> LeaveRequest:
#     """
#     Create leave request with automatic paid/unpaid calculation.
#     Coins are NOT consumed until admin approval.
#     """
#     if end_date < start_date:
#         raise ValueError("End date must be >= start date")
    
#     total_days = calculate_leave_days(start_date, end_date)
    
#     if total_days <= 0:
#         raise ValueError("Invalid leave duration")
    
#     # Calculate paid/unpaid split
#     paid_days, unpaid_days = calculate_paid_unpaid_split(db, employee_id, total_days)
    
#     leave_request = LeaveRequest(
#         employee_id=employee_id,
#         start_date=start_date,
#         end_date=end_date,
#         total_days=total_days,
#         paid_days=paid_days,
#         unpaid_days=unpaid_days,
#         leave_type=leave_type,
#         reason=reason,
#         status="pending"
#     )
    
#     db.add(leave_request)
#     db.commit()
#     db.refresh(leave_request)
    
#     return leave_request


# def approve_leave_request(
#     db: Session,
#     leave_request_id: int,
#     approved_by_user_id: int,
#     admin_notes: Optional[str] = None
# ) -> LeaveRequest:
#     """
#     Approve leave request and consume coins for paid days.
#     Recalculates split in case balance changed since request.
#     """
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    
#     if not leave:
#         raise ValueError("Leave request not found")
    
#     if leave.status == "approved":
#         raise ValueError("Leave already approved")
    
#     if leave.status == "denied":
#         raise ValueError("Cannot approve denied leave")
    
#     # Recalculate in case balance changed
#     current_paid, current_unpaid = calculate_paid_unpaid_split(
#         db, 
#         leave.employee_id, 
#         leave.total_days
#     )
    
#     leave.paid_days = current_paid
#     leave.unpaid_days = current_unpaid
    
#     # Consume coins
#     if leave.paid_days > 0:
#         consumed = consume_coins(
#             db, 
#             leave.employee_id, 
#             leave.paid_days,
#             ref_leave_request_id=leave.id
#         )
        
#         if consumed != leave.paid_days:
#             db.rollback()
#             raise ValueError(
#                 f"Insufficient balance. Required: {leave.paid_days}, Available: {consumed}"
#             )
    
#     leave.status = "approved"
#     leave.approved_by = approved_by_user_id
#     leave.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
#     leave.admin_notes = admin_notes
#     leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
#     db.commit()
#     db.refresh(leave)
    
#     return leave


# def deny_leave_request(
#     db: Session,
#     leave_request_id: int,
#     denied_by_user_id: int,
#     admin_notes: Optional[str] = None
# ) -> LeaveRequest:
#     """Deny leave request (no coins consumed)."""
#     leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    
#     if not leave:
#         raise ValueError("Leave request not found")
    
#     if leave.status == "denied":
#         raise ValueError("Leave already denied")
    
#     leave.status = "denied"
#     leave.approved_by = denied_by_user_id
#     leave.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
#     leave.admin_notes = admin_notes
#     leave.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
#     db.commit()
#     db.refresh(leave)
    
#     return leave
