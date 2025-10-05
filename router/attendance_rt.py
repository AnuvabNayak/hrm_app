# router\attendance_rt.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from db import get_db
from dependencies import get_current_user, allow_admin
from models import Employee, User, WorkSession
from services.attendance_rt import *
from services.timezone_utils import format_ist_time_12h
from zoneinfo import ZoneInfo
from schemas import WorkSessionStateOut, WorkSessionDayRow, ClockActionResponse

router = APIRouter(prefix="/attendance-rt", tags=["Attendance RT"])

@router.get("/active", response_model=WorkSessionStateOut)
def get_active(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    data = session_state(db, emp.id)
    return WorkSessionStateOut(**data)

@router.post("/clock-in", response_model=ClockActionResponse)
def post_clock_in(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = require_employee_for_user(db, current_user.id)
    ws = clock_in(db, emp.id)
    return ClockActionResponse(
        session_id=ws.id, 
        status=ws.status, 
        message=f"Clocked in at {format_ist_time_12h(ws.clock_in_time)} IST"
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

@router.post("/clock-out", response_model=ClockActionResponse)
def post_clock_out(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        emp = require_employee_for_user(db, current_user.id)
        ws = clock_out(db, emp.id)
        return ClockActionResponse(
            session_id=ws.id,
            status=ws.status,
            message=f"Clocked out at {format_ist_time_12h(ws.clock_out_time)} IST"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
