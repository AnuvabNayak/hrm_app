from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional

# ✅ FIXED: Correct imports from your dependencies.py
from dependencies import get_db, get_current_employee, get_current_user, allow_admin
from models import Employee, User

# Import service functions
from services.attendance_aggregation_service import (
    get_attendance_summary,
    get_daily_attendance,
    get_all_employees_attendance,
    aggregate_daily_attendance,
    archive_old_attendance
)

# Import schemas
from schemas import (
    DailyAttendanceOut,
    AttendanceSummaryOut
)

# Create router
router = APIRouter(
    prefix="/attendance",
    tags=["Attendance Summary"]
)


# ==============================================================================
# ENDPOINT 1: GET ATTENDANCE SUMMARY FOR DATE RANGE
# ==============================================================================
@router.get("/summary", response_model=AttendanceSummaryOut)
def get_my_attendance_summary(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)", example="2025-11-01"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)", example="2025-11-14"),
    include_archived: bool = Query(True, description="Include archived records"),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee)  # ✅ FIXED: Use get_current_employee
):
    """
    Get attendance summary for the current employee over a date range.
    """
    # ✅ FIXED: get_current_employee already returns Employee object
    # No need to query again!
    
    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate date range
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    if (end - start).days > 90:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
    
    # Get summary
    summary = get_attendance_summary(
        db=db,
        employee_id=employee.id,  # ✅ FIXED: Use employee.id directly
        start_date=start,
        end_date=end,
        include_archived=include_archived
    )
    
    return summary


# ==============================================================================
# ENDPOINT 2: GET DAILY ATTENDANCE FOR SPECIFIC DATE
# ==============================================================================
@router.get("/daily", response_model=Optional[DailyAttendanceOut])
def get_my_daily_attendance(
    attendance_date: str = Query(..., description="Date (YYYY-MM-DD)", example="2025-11-12"),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee)  # ✅ FIXED
):
    """
    Get attendance for the current employee for a specific date.
    """
    # Parse date
    try:
        target_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get daily attendance
    attendance = get_daily_attendance(
        db=db,
        employee_id=employee.id,  # ✅ FIXED
        attendance_date=target_date
    )
    
    if not attendance:
        raise HTTPException(
            status_code=404,
            detail=f"No attendance record found for {attendance_date}"
        )
    
    return attendance


# ==============================================================================
# ENDPOINT 3: GET LAST N DAYS SUMMARY (QUICK ACCESS)
# ==============================================================================
@router.get("/summary/last-{days}-days", response_model=AttendanceSummaryOut)
def get_last_n_days_summary(
    days: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee)  # ✅ FIXED
):
    """
    Quick endpoint to get summary for last N days.
    """
    # Validate days parameter
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")
    
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    # Get summary
    summary = get_attendance_summary(
        db=db,
        employee_id=employee.id,  # ✅ FIXED
        start_date=start_date,
        end_date=end_date,
        include_archived=True
    )
    
    return summary


# ==============================================================================
# ADMIN ENDPOINTS
# ==============================================================================

# ==============================================================================
# ENDPOINT 4: GET ALL EMPLOYEES ATTENDANCE FOR A DATE (ADMIN)
# ==============================================================================
@router.get("/admin/daily/all", response_model=List[DailyAttendanceOut])
def get_all_employees_daily_attendance(
    attendance_date: str = Query(..., description="Date (YYYY-MM-DD)", example="2025-11-12"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ FIXED
    _: bool = Depends(allow_admin)  # ✅ FIXED: Use allow_admin instead of require_role
):
    """
    [ADMIN ONLY] Get attendance for all employees for a specific date.
    """
    # Parse date
    try:
        target_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get all employees' attendance
    all_attendance = get_all_employees_attendance(
        db=db,
        attendance_date=target_date
    )
    
    return all_attendance


# ==============================================================================
# ENDPOINT 5: GET SPECIFIC EMPLOYEE SUMMARY (ADMIN)
# ==============================================================================
@router.get("/admin/summary/{employee_id}", response_model=AttendanceSummaryOut)
def get_employee_attendance_summary(
    employee_id: int,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    include_archived: bool = Query(True, description="Include archived records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ FIXED
    _: bool = Depends(allow_admin)  # ✅ FIXED
):
    """
    [ADMIN ONLY] Get attendance summary for a specific employee.
    """
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    
    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate date range
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")
    
    # Get summary
    summary = get_attendance_summary(
        db=db,
        employee_id=employee_id,
        start_date=start,
        end_date=end,
        include_archived=include_archived
    )
    
    return summary


# ==============================================================================
# ENDPOINT 6: MANUAL AGGREGATION TRIGGER (ADMIN)
# ==============================================================================
@router.post("/admin/aggregate")
def trigger_manual_aggregation(
    target_date: str = Query(..., description="Date to aggregate (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Specific employee ID (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ FIXED
    _: bool = Depends(allow_admin)  # ✅ FIXED
):
    """
    [ADMIN ONLY] Manually trigger aggregation for a specific date.
    """
    # Parse date
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Prevent future date aggregation
    if target > date.today():
        raise HTTPException(status_code=400, detail="Cannot aggregate future dates")
    
    # Run aggregation
    try:
        count = aggregate_daily_attendance(
            db=db,
            target_date=target,
            employee_id=employee_id
        )
        
        message = f"Successfully aggregated attendance for {target_date}"
        if employee_id:
            message += f" for employee {employee_id}"
        message += f". {count} records created/updated."
        
        return {
            "success": True,
            "message": message,
            "date": target_date,
            "employee_id": employee_id,
            "records_processed": count
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Aggregation failed: {str(e)}"
        )


# ==============================================================================
# ENDPOINT 7: MANUAL ARCHIVE TRIGGER (ADMIN)
# ==============================================================================
@router.post("/admin/archive")
def trigger_manual_archive(
    retention_days: int = Query(30, description="Archive records older than N days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ FIXED
    _: bool = Depends(allow_admin)  # ✅ FIXED
):
    """
    [ADMIN ONLY] Manually trigger archival of old daily_attendance records.
    """
    # Validate retention period
    if retention_days < 7 or retention_days > 365:
        raise HTTPException(
            status_code=400,
            detail="Retention days must be between 7 and 365"
        )
    
    # Run archive
    try:
        count = archive_old_attendance(db=db, retention_days=retention_days)
        
        return {
            "success": True,
            "message": f"Successfully archived {count} records older than {retention_days} days",
            "archived_count": count,
            "retention_days": retention_days
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Archive operation failed: {str(e)}"
        )


# ==============================================================================
# ENDPOINT 8: GET ATTENDANCE STATISTICS (ADMIN DASHBOARD)
# ==============================================================================
@router.get("/admin/statistics")
def get_attendance_statistics(
    date_param: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # ✅ FIXED
    _: bool = Depends(allow_admin)  # ✅ FIXED
):
    """
    [ADMIN ONLY] Get overall attendance statistics for a date.
    """
    # Parse date or use today
    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        target_date = date.today()
    
    # Get all attendance for date
    all_attendance = get_all_employees_attendance(db=db, attendance_date=target_date)
    
    # Calculate statistics
    total_employees = len(all_attendance)
    present_count = len([a for a in all_attendance if a.status in ['complete', 'partial']])
    absent_count = len([a for a in all_attendance if a.status == 'absent'])
    leave_count = len([a for a in all_attendance if a.status == 'leave'])
    partial_count = len([a for a in all_attendance if a.status == 'partial'])
    incomplete_count = len([a for a in all_attendance if a.status == 'incomplete'])
    
    total_work_hours = sum(a.total_work_hours for a in all_attendance)
    average_work_hours = round(total_work_hours / max(present_count, 1), 2)
    
    return {
        "date": target_date.isoformat(),
        "total_employees": total_employees,
        "present_count": present_count,
        "absent_count": absent_count,
        "leave_count": leave_count,
        "partial_count": partial_count,
        "incomplete_count": incomplete_count,
        "total_work_hours": total_work_hours,
        "average_work_hours": average_work_hours,
        "attendance_percentage": round((present_count / max(total_employees, 1)) * 100, 2)
    }