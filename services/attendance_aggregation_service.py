from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict
import logging

# Import models
from models import (
    DailyAttendance,
    ArchivedAttendance,
    WorkSession,
    Employee
)

# Import schemas
from schemas import (
    DailyAttendanceOut,
    ArchivedAttendanceOut,
    AttendanceSummaryOut
)

# Setup logging
logger = logging.getLogger(__name__)


# AGGREGATE WORK SESSIONS INTO DAILY ATTENDANCE
# ==============================================================================
def aggregate_daily_attendance(
    db: Session,
    target_date: date,
    employee_id: Optional[int] = None
) -> int:
    """
    Aggregate all work sessions for a specific date into daily_attendance.
    Runs nightly at 2:00 AM IST for previous day.
    
    Args:
        db: Database session
        target_date: Date to aggregate (typically yesterday)
        employee_id: If provided, only aggregate for this employee
    
    Returns:
        Number of daily attendance records created/updated
    
    Example:
        # Aggregate yesterday's attendance for all employees
        count = aggregate_daily_attendance(db, datetime.now().date() - timedelta(days=1))
    """
    logger.info(f"Starting aggregation for date: {target_date}, employee_id: {employee_id}")
    
    # Convert date to datetime range (start and end of day in UTC)
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    # Build base query
    query = db.query(WorkSession).filter(
        and_(
            WorkSession.clock_in_time >= start_datetime,
            WorkSession.clock_in_time <= end_datetime
        )
    )
    
    # Filter by employee if specified
    if employee_id:
        query = query.filter(WorkSession.employee_id == employee_id)
    
    # Get all work sessions for the date
    sessions = query.all()
    
    # Group sessions by employee
    employee_sessions = {}
    for session in sessions:
        if session.employee_id not in employee_sessions:
            employee_sessions[session.employee_id] = []
        employee_sessions[session.employee_id].append(session)
    
    records_created = 0
    
    # Process each employee's sessions
    for emp_id, emp_sessions in employee_sessions.items():
        # Calculate aggregated metrics
        total_work_seconds = 0
        total_break_seconds = 0
        session_count = len(emp_sessions)
        first_clock_in = None
        last_clock_out = None
        
        for session in emp_sessions:
            # Add work time
            total_work_seconds += session.total_work_seconds or 0
            
            # Calculate break time if applicable
            if session.clock_out_time:
                session_duration = (session.clock_out_time - session.clock_in_time).total_seconds()
                break_seconds = session_duration - (session.total_work_seconds or 0)
                total_break_seconds += break_seconds
            
            # Track first clock in
            if first_clock_in is None or session.clock_in_time < first_clock_in:
                first_clock_in = session.clock_in_time
            
            # Track last clock out
            if session.clock_out_time:
                if last_clock_out is None or session.clock_out_time > last_clock_out:
                    last_clock_out = session.clock_out_time
        
        # Determine status
        status = determine_attendance_status(
            total_work_seconds=total_work_seconds,
            session_count=session_count,
            last_clock_out=last_clock_out
        )
        
        # Check if daily attendance record already exists
        existing = db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.employee_id == emp_id,
                DailyAttendance.attendance_date == start_datetime
            )
        ).first()
        
        if existing:
            # Update existing record
            existing.total_work_seconds = total_work_seconds
            existing.total_break_seconds = total_break_seconds
            existing.session_count = session_count
            existing.first_clock_in = first_clock_in
            existing.last_clock_out = last_clock_out
            existing.status = status
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            logger.info(f"Updated daily attendance for employee {emp_id}, date {target_date}")
        else:
            # Create new record
            daily_attendance = DailyAttendance(
                employee_id=emp_id,
                attendance_date=start_datetime,
                total_work_seconds=total_work_seconds,
                total_break_seconds=total_break_seconds,
                session_count=session_count,
                first_clock_in=first_clock_in,
                last_clock_out=last_clock_out,
                status=status
            )
            db.add(daily_attendance)
            records_created += 1
            
            logger.info(f"Created daily attendance for employee {emp_id}, date {target_date}")
        
        # Link work sessions to daily attendance record
        # This will be done after commit when we have the daily_attendance.id
    
    db.commit()
    
    # Now link work sessions to daily attendance records
    for emp_id in employee_sessions.keys():
        daily_record = db.query(DailyAttendance).filter(
            and_(
                DailyAttendance.employee_id == emp_id,
                DailyAttendance.attendance_date == start_datetime
            )
        ).first()
        
        if daily_record:
            for session in employee_sessions[emp_id]:
                session.daily_attendance_id = daily_record.id
    
    db.commit()
    
    logger.info(f"Aggregation complete. Created/Updated {len(employee_sessions)} records")
    return records_created


# DETERMINE ATTENDANCE STATUS
# ==============================================================================
def determine_attendance_status(
    total_work_seconds: int,
    session_count: int,
    last_clock_out: Optional[datetime]
) -> str:
    """
    Determine attendance status based on work metrics.
    
    Rules:
    - complete: >= 8 hours of work, has clock out
    - partial: < 8 hours but >= 4 hours, has clock out
    - incomplete: Still clocked in (no clock out) OR < 4 hours
    - absent: 0 hours of work
    
    Args:
        total_work_seconds: Total work time in seconds
        session_count: Number of clock in/out sessions
        last_clock_out: Last clock out time (None if still clocked in)
    
    Returns:
        Status string: complete, partial, incomplete, or absent
    """
    # No work sessions
    if session_count == 0 or total_work_seconds == 0:
        return "absent"
    
    # Still clocked in (no clock out on last session)
    if last_clock_out is None:
        return "incomplete"
    
    # Convert to hours
    work_hours = total_work_seconds / 3600
    
    # Determine status based on hours
    if work_hours >= 8.0:
        return "complete"
    elif work_hours >= 4.0:
        return "partial"
    else:
        return "incomplete"


# ARCHIVE OLD DAILY ATTENDANCE
# ==============================================================================
def archive_old_attendance(
    db: Session,
    retention_days: int = 30
) -> int:
    """
    Move daily attendance records older than retention_days to archive.
    Runs nightly at 2:45 AM IST (after aggregation).
    
    Args:
        db: Database session
        retention_days: Keep this many days in hot storage (default: 30)
    
    Returns:
        Number of records archived
    
    Example:
        # Archive attendance older than 30 days
        count = archive_old_attendance(db, retention_days=30)
    """
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    
    logger.info(f"Starting archival for records older than {cutoff_date.date()}")
    
    # Find records to archive
    old_records = db.query(DailyAttendance).filter(
        DailyAttendance.attendance_date < cutoff_date
    ).all()
    
    archived_count = 0
    
    for record in old_records:
        # Create archived record
        archived = ArchivedAttendance(
            employee_id=record.employee_id,
            attendance_date=record.attendance_date,
            total_work_seconds=record.total_work_seconds,
            total_break_seconds=record.total_break_seconds,
            session_count=record.session_count,
            first_clock_in=record.first_clock_in,
            last_clock_out=record.last_clock_out,
            status=record.status,
            original_daily_id=record.id
        )
        db.add(archived)
        
        # Delete from daily_attendance
        db.delete(record)
        archived_count += 1
    
    db.commit()
    
    logger.info(f"Archived {archived_count} records")
    return archived_count


# DELETE OLD ARCHIVED ATTENDANCE
# ==============================================================================
def delete_old_archived_attendance(
    db: Session,
    retention_days: int = 365
) -> int:
    """
    Delete archived attendance records older than retention period.
    Runs monthly to maintain database size.
    
    Args:
        db: Database session
        retention_days: Keep archived records for this many days (default: 365 = 1 year)
    
    Returns:
        Number of records deleted
    
    Example:
        # Delete archived records older than 1 year
        count = delete_old_archived_attendance(db, retention_days=365)
    """
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    
    logger.info(f"Starting deletion of archived records older than {cutoff_date.date()}")
    
    # Delete old archived records
    deleted = db.query(ArchivedAttendance).filter(
        ArchivedAttendance.attendance_date < cutoff_date
    ).delete()
    
    db.commit()
    
    logger.info(f"Deleted {deleted} old archived records")
    return deleted


# GET ATTENDANCE SUMMARY FOR DATE RANGE
# ==============================================================================
def get_attendance_summary(
    db: Session,
    employee_id: int,
    start_date: date,
    end_date: date,
    include_archived: bool = True
) -> AttendanceSummaryOut:
    """
    Get attendance summary for an employee over a date range.
    Combines daily_attendance and archived_attendance if needed.
    
    Args:
        db: Database session
        employee_id: Employee to get summary for
        start_date: Start of date range
        end_date: End of date range
        include_archived: Whether to include archived records
    
    Returns:
        AttendanceSummaryOut schema with summary and daily records
    
    Example:
        # Get last 14 days of attendance
        summary = get_attendance_summary(
            db, 
            employee_id=5,
            start_date=datetime.now().date() - timedelta(days=14),
            end_date=datetime.now().date()
        )
    """
    # Convert dates to datetime
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get daily attendance records
    daily_records = db.query(DailyAttendance).filter(
        and_(
            DailyAttendance.employee_id == employee_id,
            DailyAttendance.attendance_date >= start_datetime,
            DailyAttendance.attendance_date <= end_datetime
        )
    ).order_by(desc(DailyAttendance.attendance_date)).all()
    
    # Get archived records if requested
    archived_records = []
    if include_archived:
        archived_records = db.query(ArchivedAttendance).filter(
            and_(
                ArchivedAttendance.employee_id == employee_id,
                ArchivedAttendance.attendance_date >= start_datetime,
                ArchivedAttendance.attendance_date <= end_datetime
            )
        ).order_by(desc(ArchivedAttendance.attendance_date)).all()
    
    # Combine and calculate summary
    all_records = daily_records + archived_records
    
    # Calculate metrics
    total_days = (end_date - start_date).days + 1
    days_present = len([r for r in all_records if r.status in ['complete', 'partial']])
    days_absent = len([r for r in all_records if r.status == 'absent'])
    days_on_leave = len([r for r in all_records if r.status == 'leave'])
    days_partial = len([r for r in all_records if r.status == 'partial'])
    
    total_work_seconds = sum(r.total_work_seconds for r in all_records)
    total_break_seconds = sum(r.total_break_seconds for r in all_records)
    
    total_work_hours = round(total_work_seconds / 3600, 2)
    total_break_hours = round(total_break_seconds / 3600, 2)
    average_work_hours_per_day = round(total_work_hours / max(days_present, 1), 2)
    
    # Status breakdown
    status_breakdown = {}
    for record in all_records:
        status_breakdown[record.status] = status_breakdown.get(record.status, 0) + 1
    
    # Convert to schemas
    daily_out = [DailyAttendanceOut.model_validate(r) for r in daily_records]
    archived_out = [ArchivedAttendanceOut.model_validate(r) for r in archived_records]
    
    return AttendanceSummaryOut(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        employee_id=employee_id,
        total_days=total_days,
        days_present=days_present,
        days_absent=days_absent,
        days_on_leave=days_on_leave,
        days_partial=days_partial,
        total_work_hours=total_work_hours,
        total_break_hours=total_break_hours,
        average_work_hours_per_day=average_work_hours_per_day,
        daily_records=daily_out,
        archived_records=archived_out,
        status_breakdown=status_breakdown
    )


# GET DAILY ATTENDANCE FOR EMPLOYEE
# ==============================================================================
def get_daily_attendance(
    db: Session,
    employee_id: int,
    attendance_date: date
) -> Optional[DailyAttendanceOut]:
    """
    Get daily attendance for a specific employee and date.
    Checks daily_attendance first, then archived_attendance.
    
    Args:
        db: Database session
        employee_id: Employee ID
        attendance_date: Date to get attendance for
    
    Returns:
        DailyAttendanceOut if found, None otherwise
    
    Example:
        # Get today's attendance
        attendance = get_daily_attendance(db, employee_id=5, attendance_date=datetime.now().date())
    """
    # Convert date to datetime
    target_datetime = datetime.combine(attendance_date, datetime.min.time())
    
    # Check daily_attendance first
    record = db.query(DailyAttendance).filter(
        and_(
            DailyAttendance.employee_id == employee_id,
            DailyAttendance.attendance_date == target_datetime
        )
    ).first()
    
    if record:
        return DailyAttendanceOut.model_validate(record)
    
    # Check archived_attendance if not found
    archived = db.query(ArchivedAttendance).filter(
        and_(
            ArchivedAttendance.employee_id == employee_id,
            ArchivedAttendance.attendance_date == target_datetime
        )
    ).first()
    
    if archived:
        # Convert ArchivedAttendance to DailyAttendanceOut format
        return ArchivedAttendanceOut.model_validate(archived)
    
    return None


# GET ALL EMPLOYEES DAILY ATTENDANCE
# ==============================================================================
def get_all_employees_attendance(
    db: Session,
    attendance_date: date
) -> List[DailyAttendanceOut]:
    """
    Get daily attendance for all employees for a specific date.
    Used by admin dashboard.
    
    Args:
        db: Database session
        attendance_date: Date to get attendance for
    
    Returns:
        List of DailyAttendanceOut for all employees
    
    Example:
        # Get today's attendance for all employees
        all_attendance = get_all_employees_attendance(db, datetime.now().date())
    """
    target_datetime = datetime.combine(attendance_date, datetime.min.time())
    
    records = db.query(DailyAttendance).filter(
        DailyAttendance.attendance_date == target_datetime
    ).all()
    
    return [DailyAttendanceOut.model_validate(r) for r in records]

# UPDATE DAILY ATTENDANCE AFTER CLOCK-OUT
# ==============================================================================
def update_daily_attendance(
    db: Session,
    employee_id: int,
    target_date: date
) -> int:
    """
    Update daily attendance after clock-out (wrapper for aggregate_daily_attendance).
    
    Called immediately after employee clocks out to ensure daily record is up-to-date.
    
    Args:
        db: Database session
        employee_id: Employee who just clocked out
        target_date: Date of clock-out (usually today)
        
    Returns:
        Number of records created/updated
    """
    logger.info(f"Updating daily attendance for employee {employee_id} on {target_date}")
    return aggregate_daily_attendance(
        db=db,
        target_date=target_date,
        employee_id=employee_id
    )
