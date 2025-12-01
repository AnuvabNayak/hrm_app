# router\attendance_rt.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional
from db import get_db
from dependencies import get_current_user, allow_admin
from models import Employee, User, WorkSession, DailyAttendance, Department
from services.attendance_rt import *
from services.attendance_rt import _sum_breaks
from services.timezone_utils import format_ist_time_12h, utc_now, format_ist_datetime
from zoneinfo import ZoneInfo
from schemas import WorkSessionStateOut, WorkSessionDayRow, ClockActionResponse
from schemas import (
    AttendanceAdjustmentRequest,
    AttendanceAdjustmentOut,
    AttendanceAdjustmentHistoryOut
)
from schemas import ClockInRequest, ClockOutRequest, WorkSessionOut
router = APIRouter(prefix="/attendance-rt", tags=["Attendance RT"])

import logging

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@router.get("/active", response_model=WorkSessionStateOut)
def get_active(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    data = session_state(db, emp.id)
    return WorkSessionStateOut(**data)

# @router.post("/clock-in", response_model=ClockActionResponse)
# def post_clock_in(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     emp = require_employee_for_user(db, current_user.id)
#     ws = clock_in(db, emp.id)
#     return ClockActionResponse(
#         session_id=ws.id, 
#         status=ws.status, 
#         message=f"Clocked in at {format_ist_time_12h(ws.clock_in_time)} IST"
#     )


# ENHANCED CLOCK-IN WITH WORK NOTES

@router.post("/attendance/clock-in", response_model=WorkSessionOut)
def clock_in_with_notes(
    request: ClockInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clock in with work plan and department selection.
    
    **New Features:**
    - Requires department selection (dropdown in frontend)
    - Requires work plan (minimum 10 characters)
    - Stores both in work_sessions table for tracking
    
    **Validations:**
    - No active or break session exists
    - Department ID is valid and active
    - Work plan not empty and meets length requirements
    
    **Returns:**
    - Complete work session details including work notes
    
    **Use Cases:**
    - Employee starts work day
    - Employee returns after completing previous session
    - Multiple clock-ins per day supported (each with own work plan)
    """
    # Get employee profile
    employee = db.query(Employee).filter(
        Employee.user_id == current_user.id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=404, 
            detail="Employee profile not found. Please contact administrator."
        )
    
    # Check for active or break session
    active_session = db.query(WorkSession).filter(
        WorkSession.employee_id == employee.id,
        WorkSession.status.in_(["active", "break"])
    ).first()
    
    if active_session:
        raise HTTPException(
            status_code=400,
            detail=f"You already have an active session (status: {active_session.status}). "
                   f"Please clock out from your current session first."
        )
    
    # Validate department exists and is active
    department = db.query(Department).filter(
        Department.id == request.department_id,
        Department.is_active == True
    ).first()
    
    if not department:
        raise HTTPException(
            status_code=404,
            detail=f"Department with ID {request.department_id} not found or inactive. "
                   f"Please select a valid department."
        )
    
    # Create new work session with notes
    # now = datetime.now(timezone.utc).replace(tzinfo=None)
    now = utc_now()
    
    new_session = WorkSession(
        employee_id=employee.id,
        clock_in_time=now,
        status="active",
        department_id=request.department_id,
        work_plan=request.work_plan,
        notes_updated_at=now
    )
    
    db.add(new_session)
    
    try:
        db.commit()
        db.refresh(new_session)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create work session for employee {employee.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clock in. Please try again. Error: {str(e)}"
        )
    
    logger.info(
        f"✓ Employee {employee.name} (ID: {employee.id}) clocked in successfully. "
        f"Department: {department.name}, Session ID: {new_session.id}"
    )
    
    # Prepare response
    return WorkSessionOut(
        id=new_session.id,
        employee_id=new_session.employee_id,
        clock_in_time=new_session.clock_in_time,
        clock_out_time=new_session.clock_out_time,
        status=new_session.status,
        total_work_seconds=new_session.total_work_seconds,
        department_id=new_session.department_id,
        department_name=department.name,
        work_plan=new_session.work_plan,
        tasks_completed=new_session.tasks_completed,
        notes_updated_at=new_session.notes_updated_at
    )




@router.post("/start-break", response_model=ClockActionResponse)
def post_start_break(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    try:
        ws = start_break(db, emp.id)
        db.commit()
        return ClockActionResponse(session_id=ws.id, status=ws.status, message="Break started")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/stop-break", response_model=ClockActionResponse)
def post_stop_break(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    try:
        ws = stop_break(db, emp.id)
        db.commit()
        return ClockActionResponse(session_id=ws.id, status=ws.status, message="Break stopped")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.post("/clock-out", response_model=ClockActionResponse)
# def post_clock_out(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         emp = require_employee_for_user(db, current_user.id)
#         ws = clock_out(db, emp.id)
#         return ClockActionResponse(
#             session_id=ws.id,
#             status=ws.status,
#             message=f"Clocked out at {format_ist_time_12h(ws.clock_out_time)} IST"
#         )
#     except RuntimeError as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ENHANCED CLOCK-OUT WITH COMPLETED TASKS

@router.post("/attendance/clock-out", response_model=WorkSessionOut)
def clock_out_with_notes(
    request: ClockOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clock out with completed tasks description.
    
    **New Features:**
    - Requires tasks completed (minimum 10 characters)
    - Updates work_sessions table with completion notes
    - Maintains department from clock-in (no need to re-select)
    - Calculates total work time (excluding breaks)
    
    **Validations:**
    - Active session exists (user must be clocked in)
    - Tasks completed not empty and meets length requirements
    
    **Returns:**
    - Complete work session details including both work plan and tasks completed
    
    **Side Effects:**
    - Updates daily attendance aggregation
    - Marks session as 'ended'
    - Deducts break time from total work time
    """
    # Get employee profile
    employee = db.query(Employee).filter(
        Employee.user_id == current_user.id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=404, 
            detail="Employee profile not found. Please contact administrator."
        )
    
    # Find active session
    active_session = db.query(WorkSession).filter(
        WorkSession.employee_id == employee.id,
        WorkSession.status == "active"
    ).first()
    
    if not active_session:
        raise HTTPException(
            status_code=400,
            detail="No active clock-in session found. Please clock in first."
        )
    
    # Update session with clock-out and completed tasks
    # now = datetime.now(timezone.utc).replace(tzinfo=None)
    now = utc_now()
    
    active_session.clock_out_time = now
    active_session.status = "ended"
    active_session.tasks_completed = request.tasks_completed
    active_session.notes_updated_at = now
    
    # Calculate total work seconds (excluding breaks)
    total_seconds = (now - active_session.clock_in_time).total_seconds()
    
    # Get total break time for this session
    break_time = db.query(func.sum(
        func.extract('epoch', BreakInterval.end_time - BreakInterval.start_time)
    )).filter(
        BreakInterval.session_id == active_session.id,
        BreakInterval.end_time.isnot(None)
    ).scalar() or 0
    
    active_session.total_work_seconds = int(total_seconds - break_time)
    
    try:
        db.commit()
        db.refresh(active_session)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clock out for employee {employee.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clock out. Please try again. Error: {str(e)}"
        )
    
    # Update daily attendance aggregation
    try:
        from services.attendance_aggregation_service import update_daily_attendance
        update_daily_attendance(db, employee.id, active_session.clock_in_time.date())
    except Exception as e:
        logger.warning(f"Failed to update daily attendance: {str(e)}")
        # Don't fail the clock-out if aggregation fails
    
    logger.info(
        f"✓ Employee {employee.name} (ID: {employee.id}) clocked out successfully. "
        f"Total work: {active_session.total_work_seconds / 3600:.2f} hours, "
        f"Session ID: {active_session.id}"
    )
    
    # Get department name for response
    department_name = None
    if active_session.department_id:
        dept = db.query(Department).filter(
            Department.id == active_session.department_id
        ).first()
        if dept:
            department_name = dept.name
    
    return WorkSessionOut(
        id=active_session.id,
        employee_id=active_session.employee_id,
        clock_in_time=active_session.clock_in_time,
        clock_out_time=active_session.clock_out_time,
        status=active_session.status,
        total_work_seconds=active_session.total_work_seconds,
        department_id=active_session.department_id,
        department_name=department_name,
        work_plan=active_session.work_plan,
        tasks_completed=active_session.tasks_completed,
        notes_updated_at=active_session.notes_updated_at
    )





@router.get("/recent", response_model=list[WorkSessionDayRow])
def get_recent(days: int = 14, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    data = sessions_last_days(db, emp.id, days)
    return [WorkSessionDayRow(**row) for row in data]

@router.get("/today-completed")
def get_today_completed_sessions(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get completed work sessions for today only"""
    emp = require_employee_for_user(db, current_user.id)
    return get_today_completed_work(db, emp.id)

@router.get("/timesheet")
def get_timesheet_history(
    days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get last 14 days attendance history for timesheet"""
    try:
        emp = require_employee_for_user(db, current_user.id)
        
        # Get last 14 days of completed sessions
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        sessions = (
            db.query(WorkSession)
            .filter(
                WorkSession.employee_id == emp.id,
                WorkSession.clock_in_time >= cutoff.replace(tzinfo=None),
                WorkSession.status == "ended"  # Only completed sessions
            )
            .order_by(WorkSession.clock_in_time.desc())
            .all()
        )
        
        IST = ZoneInfo("Asia/Kolkata")
        
        results = []
        for session in sessions:
            # Convert to IST for display
            clock_in_ist = session.clock_in_time.replace(tzinfo=timezone.utc).astimezone(IST)
            clock_out_ist = session.clock_out_time.replace(tzinfo=timezone.utc).astimezone(IST) if session.clock_out_time else None
            
            # Calculate break duration using the imported function
            break_seconds = _sum_breaks(db, session.id) or 0
            
            # Format durations
            work_hours = (session.total_work_seconds or 0) // 3600
            work_minutes = ((session.total_work_seconds or 0) % 3600) // 60
            
            break_hours = break_seconds // 3600
            break_minutes = (break_seconds % 3600) // 60
            
            results.append({
                "id": session.id,
                "date": clock_in_ist.strftime("%a, %d"),  # "Tue, 01"
                "full_date": clock_in_ist.strftime("%Y-%m-%d"),
                "day_name": clock_in_ist.strftime("%A"),  # "Tuesday"
                "clock_in_time": clock_in_ist.strftime("%I:%M %p"),  # "9:53 AM"
                "clock_out_time": clock_out_ist.strftime("%I:%M %p") if clock_out_ist else "-",
                "work_duration": f"{work_hours}h {work_minutes}m",  # "10h 7m"
                "break_duration": f"{break_hours}h {break_minutes}m",  # "0h 53m"
                "status": "ON TIME" if work_hours >= 8 else "PARTIAL",  # Basic status logic
                "shift_info": f"Shift - {clock_in_ist.strftime('%I:%M %p')} - {clock_out_ist.strftime('%I:%M %p') if clock_out_ist else 'Active'}"
            })
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch timesheet data: {str(e)}")

# Admin endpoints have been added below

@router.get("/admin/all-employees-status", dependencies=[Depends(allow_admin)])
def admin_all_employees_status(db: Session = Depends(get_db)):
    """
    Get current status of all employees, including username via an explicit join.
    """
    # Join Employee -> User on Employee.user_id == User.id
    rows = (
        db.query(
            Employee.id.label("employee_id"),
            Employee.name.label("employee_name"),
            Employee.emp_code.label("emp_code"),
            User.username.label("username")
        )
        .join(User, Employee.user_id == User.id)
        .all()
    )

    result = []
    for r in rows:
        status_data = session_state(db, r.employee_id)  # existing helper
        result.append({
            "employee_id": r.employee_id,
            "employee_name": r.employee_name,
            "username": r.username,
            "emp_code": r.emp_code,
            "current_status": status_data["status"],
            "clock_in_time": status_data["clock_in_time"],
            "elapsed_work_seconds": status_data["elapsed_work_seconds"],
            "elapsed_break_seconds": status_data["elapsed_break_seconds"],
        })
    return result

@router.get("/admin/employee/{employee_id}/recent", dependencies=[Depends(allow_admin)])
def admin_employee_attendance(
    employee_id: int, 
    days: int = Query(14, le=90), 
    db: Session = Depends(get_db)
):
    """Get specific employee's attendance history"""
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return sessions_last_days(db, employee_id, days)

@router.post("/admin/employee/{employee_id}/clock-in", dependencies=[Depends(allow_admin)])
def admin_clock_in_employee(employee_id: int, db: Session = Depends(get_db)):
    """Admin clock in an employee"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    try:
        session = clock_in(db, employee_id)
        db.commit()
        return {"message": f"Clocked in {employee.name}", "session_id": session.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admin/employee/{employee_id}/clock-out", dependencies=[Depends(allow_admin)])
def admin_clock_out_employee(employee_id: int, db: Session = Depends(get_db)):
    """Admin clock out an employee"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    try:
        session = clock_out(db, employee_id)
        db.commit()
        return {"message": f"Clocked out {employee.name}", "total_work_seconds": session.total_work_seconds}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# MANUAL ATTENDANCE ADJUSTMENT ENDPOINTS
# Purpose: Allow Admin to manually correct attendance records

@router.put(
    "/admin/attendance/{attendance_id}/adjust", 
    response_model=AttendanceAdjustmentOut,
    dependencies=[Depends(allow_admin)],
    summary="Manually adjust daily attendance record",
    description="""
    Manually adjust daily attendance record for missed or incorrect clock in/out times.
    
    **Admin Only Endpoint**
    
    **Use Cases:**
    - Employee forgot to clock in/out
    - System error during attendance recording
    - Manual correction needed for compliance
    
    **Validations:**
    - `last_clock_out` must be after `first_clock_in`
    - Work hours recalculated automatically
    - Status updated based on new work hours
    - Adjustment reason is mandatory (minimum 10 characters)
    - Creates complete audit trail
    
    **Returns:**
    Complete adjusted attendance record with adjustment metadata
    """,
    tags=["Admin - Attendance Adjustments"]
)
def adjust_daily_attendance(
    attendance_id: int,
    adjustment: AttendanceAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually adjust daily attendance record with full audit trail.
    
    Args:
        attendance_id: ID of the daily attendance record to adjust
        adjustment: Adjustment details (clock times and reason)
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        AttendanceAdjustmentOut: Complete adjusted attendance record
    
    Raises:
        HTTPException 404: Attendance record or employee not found
        HTTPException 400: Invalid time validation (clock-out before clock-in)
        HTTPException 500: Database error during save
    """
    # Fetch and validate attendance record
    attendance = db.query(DailyAttendance).filter(
        DailyAttendance.id == attendance_id
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=404, 
            detail=f"Attendance record with ID {attendance_id} not found"
        )
    
    # Fetch employee details
    employee = db.query(Employee).filter(
        Employee.id == attendance.employee_id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found for this attendance record"
        )
    
    # Additional validation - clock_out must be after clock_in
    if adjustment.first_clock_in and adjustment.last_clock_out:
        if adjustment.last_clock_out <= adjustment.first_clock_in:
            raise HTTPException(
                status_code=400,
                detail="Last clock out time must be after first clock in time"
            )
    
    # Apply adjustments
    if adjustment.first_clock_in:
        attendance.first_clock_in = adjustment.first_clock_in
    
    if adjustment.last_clock_out:
        attendance.last_clock_out = adjustment.last_clock_out
    
    # Recalculate work hours and status
    if attendance.first_clock_in and attendance.last_clock_out:
        # Calculate total seconds between first clock-in and last clock-out
        total_seconds = (attendance.last_clock_out - attendance.first_clock_in).total_seconds()
        
        # Subtract break time
        attendance.total_work_seconds = int(total_seconds - (attendance.total_break_seconds or 0))
        
        # Recalculate status based on work hours
        work_hours = attendance.total_work_seconds / 3600
        
        if work_hours >= 8:
            attendance.status = "complete"
        elif work_hours >= 4:
            attendance.status = "partial"
        elif work_hours > 0:
            attendance.status = "incomplete"
        else:
            attendance.status = "absent"
    
    # Mark as manually adjusted with audit information
    attendance.is_manually_adjusted = True
    attendance.adjusted_by_user_id = current_user.id
    attendance.adjustment_reason = adjustment.reason
    attendance.adjusted_at = datetime.now(timezone.utc)
    attendance.updated_at = datetime.now(timezone.utc)
    
    # Save changes to database
    try:
        db.commit()
        db.refresh(attendance)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save attendance adjustment: {str(e)}"
        )
    
    # Prepare and return response
    return AttendanceAdjustmentOut(
        id=attendance.id,
        employee_id=employee.id,
        employee_name=employee.name,
        emp_code=employee.emp_code,
        attendance_date=attendance.attendance_date,
        first_clock_in=attendance.first_clock_in,
        last_clock_out=attendance.last_clock_out,
        total_work_hours=round(attendance.total_work_seconds / 3600, 2) if attendance.total_work_seconds else 0.0,
        total_break_hours=round(attendance.total_break_seconds / 3600, 2) if attendance.total_break_seconds else 0.0,
        status=attendance.status,
        is_manually_adjusted=attendance.is_manually_adjusted,
        adjustment_reason=attendance.adjustment_reason,
        adjusted_by_username=current_user.username,
        adjusted_at=attendance.adjusted_at
    )

@router.get(
    "/admin/attendance/adjustments", 
    response_model=List[AttendanceAdjustmentHistoryOut],
    dependencies=[Depends(allow_admin)],
    summary="Get attendance adjustment history",
    description="""
    Retrieve complete audit trail of manual attendance adjustments.
    
    **Admin Only Endpoint**
    
    **Use Cases:**
    - Compliance audits and reporting
    - Manager oversight and accountability
    - Identifying patterns of attendance issues
    - Generating adjustment reports for HR
    
    **Query Parameters:**
    - `start_date`: Filter from this date (YYYY-MM-DD) - Required
    - `end_date`: Filter until this date (YYYY-MM-DD) - Required
    - `department_id`: Optional department filter
    
    **Returns:**
    List of adjustment records with full audit details, ordered by most recent first
    """,
    tags=["Admin - Attendance Adjustments"]
)
def get_adjustment_history(
    start_date: date = Query(..., description="Start date for history (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for history (YYYY-MM-DD)"),
    department_id: Optional[int] = Query(None, description="Optional department filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(allow_admin)
):
    """
    Get history of manual attendance adjustments for audit and compliance.
    
    Args:
        start_date: Start date for filtering adjustments
        end_date: End date for filtering adjustments
        department_id: Optional filter by department
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        List[AttendanceAdjustmentHistoryOut]: List of adjustment history records
    
    Raises:
        HTTPException 400: Invalid date range (end before start)
    """
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must be after start date"
        )
    
    # Build base query with joins
    query = db.query(
        DailyAttendance.attendance_date,
        Employee.name.label("employee_name"),
        Employee.emp_code,
        Department.name.label("department"),
        User.username.label("adjusted_by"),
        DailyAttendance.adjustment_reason,
        DailyAttendance.adjusted_at
    ).join(
        Employee, DailyAttendance.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).join(
        User, DailyAttendance.adjusted_by_user_id == User.id
    ).filter(
        DailyAttendance.is_manually_adjusted == True,
        DailyAttendance.attendance_date.between(start_date, end_date)
    )
    
    # Apply optional department filter
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    # Order by most recent adjustments first
    query = query.order_by(DailyAttendance.adjusted_at.desc())
    
    # Execute query and fetch results
    results = query.all()
    
    # Format and return response
    return [
        AttendanceAdjustmentHistoryOut(
            attendance_date=r.attendance_date.date() if isinstance(r.attendance_date, datetime) else r.attendance_date,
            employee_name=r.employee_name,
            emp_code=r.emp_code,
            department=r.department,
            adjusted_by=r.adjusted_by,
            adjustment_reason=r.adjustment_reason,
            adjusted_at=r.adjusted_at
        )
        for r in results
    ]




# ============================================================================
# WORK NOTES QUERY ENDPOINTS (NEW - Added 2025-11-26)
# ============================================================================

@router.get("/attendance/work-notes/today", response_model=WorkSessionOut)
def get_today_work_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get today's work notes (latest session).
    
    Returns the most recent work session for today, including:
    - Work plan entered at clock-in
    - Tasks completed entered at clock-out
    - Department information
    - Session timing and duration
    
    **Use Case:**
    - Display today's work summary on dashboard
    - Show what was planned vs completed
    """
    employee = db.query(Employee).filter(
        Employee.user_id == current_user.id
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    today = datetime.now(timezone.utc).date()
    
    # Get latest session for today
    session = db.query(WorkSession).filter(
        WorkSession.employee_id == employee.id,
        func.date(WorkSession.clock_in_time) == today
    ).order_by(WorkSession.clock_in_time.desc()).first()
    
    if not session:
        raise HTTPException(
            status_code=404, 
            detail="No work session found for today. Please clock in first."
        )
    
    # Get department name
    department_name = None
    if session.department_id:
        dept = db.query(Department).filter(Department.id == session.department_id).first()
        if dept:
            department_name = dept.name
    
    return WorkSessionOut(
        id=session.id,
        employee_id=session.employee_id,
        clock_in_time=session.clock_in_time,
        clock_out_time=session.clock_out_time,
        status=session.status,
        total_work_seconds=session.total_work_seconds,
        department_id=session.department_id,
        department_name=department_name,
        work_plan=session.work_plan,
        tasks_completed=session.tasks_completed,
        notes_updated_at=session.notes_updated_at
    )


@router.get("/attendance/work-notes/history", response_model=List[WorkSessionOut])
def get_work_notes_history(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work notes history for date range.
    
    Returns all work sessions with notes for the specified date range.
    Useful for:
    - Timesheet review
    - Performance tracking
    - Work pattern analysis
    
    **Parameters:**
    - start_date: Beginning of date range
    - end_date: End of date range (inclusive)
    
    **Returns:**
    - List of work sessions ordered by most recent first
    """
    employee = db.query(Employee).filter(
        Employee.user_id == current_user.id
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must be after or equal to start date"
        )
    
    # Query sessions with notes
    sessions = db.query(WorkSession).filter(
        WorkSession.employee_id == employee.id,
        func.date(WorkSession.clock_in_time) >= start_date,
        func.date(WorkSession.clock_in_time) <= end_date
    ).order_by(WorkSession.clock_in_time.desc()).all()
    
    # Build response with department names
    result = []
    for session in sessions:
        department_name = None
        if session.department_id:
            dept = db.query(Department).filter(
                Department.id == session.department_id
            ).first()
            if dept:
                department_name = dept.name
        
        result.append(WorkSessionOut(
            id=session.id,
            employee_id=session.employee_id,
            clock_in_time=session.clock_in_time,
            clock_out_time=session.clock_out_time,
            status=session.status,
            total_work_seconds=session.total_work_seconds,
            department_id=session.department_id,
            department_name=department_name,
            work_plan=session.work_plan,
            tasks_completed=session.tasks_completed,
            notes_updated_at=session.notes_updated_at
        ))
    
    return result


# ADMIN: VIEW EMPLOYEE WORK NOTES

@router.get(
    "/admin/work-notes/{employee_id}",
    response_model=List[WorkSessionOut],
    dependencies=[Depends(allow_admin)],
    summary="Admin: View employee work notes",
    tags=["Admin - Attendance"]
)
def admin_get_employee_work_notes(
    employee_id: int,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to view any employee's work notes.
    
    **Admin Only** - Requires admin or super_admin role
    
    Useful for:
    - Performance review
    - Work verification
    - Productivity analysis
    - Attendance disputes
    
    **Parameters:**
    - employee_id: ID of employee to query
    - start_date: Beginning of date range
    - end_date: End of date range (inclusive)
    
    **Returns:**
    - List of work sessions with complete work notes
    """
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=404, 
            detail=f"Employee with ID {employee_id} not found"
        )
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must be after or equal to start date"
        )
    
    # Query sessions
    sessions = db.query(WorkSession).filter(
        WorkSession.employee_id == employee_id,
        func.date(WorkSession.clock_in_time) >= start_date,
        func.date(WorkSession.clock_in_time) <= end_date
    ).order_by(WorkSession.clock_in_time.desc()).all()
    
    # Build response
    result = []
    for session in sessions:
        department_name = None
        if session.department_id:
            dept = db.query(Department).filter(
                Department.id == session.department_id
            ).first()
            if dept:
                department_name = dept.name
        
        result.append(WorkSessionOut(
            id=session.id,
            employee_id=session.employee_id,
            clock_in_time=session.clock_in_time,
            clock_out_time=session.clock_out_time,
            status=session.status,
            total_work_seconds=session.total_work_seconds,
            department_id=session.department_id,
            department_name=department_name,
            work_plan=session.work_plan,
            tasks_completed=session.tasks_completed,
            notes_updated_at=session.notes_updated_at
        ))
    
    logger.info(
        f"Admin queried work notes for employee {employee.name} (ID: {employee_id}). "
        f"Date range: {start_date} to {end_date}, Found: {len(result)} sessions"
    )
    
    return result
