# services/attendance_rt.py
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import WorkSession, BreakInterval, Employee
from .timezone_utils import (
    utc_now, format_ist_datetime, format_ist_time_12h, 
    format_ist_date, debug_timezone_info
)

# IST Timezone Utilities
def _ist_timezone():
    """Return IST timezone object (UTC+5:30)"""
    return timezone(timedelta(hours=5, minutes=30))

def _utc_to_ist(utc_dt):
    """Convert UTC datetime to IST"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(_ist_timezone())

def _ist_format(utc_dt):
    """Format UTC datetime as IST string for API responses"""
    if utc_dt is None:
        return None
    ist_dt = _utc_to_ist(utc_dt)
    return ist_dt.strftime("%Y-%m-%d %H:%M:%S")

def _utc_now():
    return utc_now()  # Use universal utility

# def _utc_now():
#     return datetime.now(timezone.utc).replace(tzinfo=None)  # store naive UTC

def _sum_breaks(db: Session, session_id: int, as_of: datetime | None = None) -> int:
    as_of = as_of or _utc_now()
    intervals = db.query(BreakInterval).filter(BreakInterval.session_id == session_id).all()
    total = 0
    for b in intervals:
        if b.end_time:
            total += int((b.end_time - b.start_time).total_seconds())
        else:
            total += int((as_of - b.start_time).total_seconds())
    return max(total, 0)

def _elapsed_work_seconds(clock_in: datetime, breaks_seconds: int, clock_out: datetime | None = None, as_of: datetime | None = None) -> int:
    end = clock_out or (as_of or _utc_now())
    gross = int((end - clock_in).total_seconds())
    return max(gross - breaks_seconds, 0)

def get_active_session(db: Session, employee_id: int) -> WorkSession | None:
    return (
        db.query(WorkSession)
        .filter(WorkSession.employee_id == employee_id, WorkSession.status.in_(["active", "break"]))
        .order_by(WorkSession.id.desc())
        .first()
    )

def require_employee_for_user(db: Session, user_id: int) -> Employee:
    emp = db.query(Employee).filter(Employee.user_id == user_id).first()
    if not emp:
        raise ValueError("Employee profile not found")
    return emp

def clock_in(db: Session, employee_id: int) -> WorkSession:
    existing = get_active_session(db, employee_id)
    if existing:
        return existing
    
    now = _utc_now()
    ws = WorkSession(employee_id=employee_id, clock_in_time=now, status="active", total_work_seconds=0)
    db.add(ws)
    db.commit()  # COMMIT instead of flush
    db.refresh(ws)  # Refresh to get the ID
    return ws


def start_break(db: Session, employee_id: int) -> WorkSession:
    ws = get_active_session(db, employee_id)
    if not ws or ws.status == "ended":
        raise RuntimeError("No active session to start break")
    if ws.status == "break":
        return ws
    now = _utc_now()
    bi = BreakInterval(session_id=ws.id, start_time=now)
    db.add(bi)
    ws.status = "break"
    db.add(ws)
    return ws

def stop_break(db: Session, employee_id: int) -> WorkSession:
    ws = get_active_session(db, employee_id)
    if not ws or ws.status != "break":
        raise RuntimeError("No break in progress")
    now = _utc_now()
    open_break = (
        db.query(BreakInterval)
        .filter(BreakInterval.session_id == ws.id, BreakInterval.end_time.is_(None))
        .order_by(BreakInterval.id.desc())
        .first()
    )
    if not open_break:
        raise RuntimeError("Break state inconsistent")
    open_break.end_time = now
    db.add(open_break)
    ws.status = "active"
    db.add(ws)
    return ws

def clock_out(db: Session, employee_id: int) -> WorkSession:
    ws = get_active_session(db, employee_id)
    if not ws or ws.status == "ended":
        raise RuntimeError("No active session to clock out")

    now = _utc_now()
    if ws.status == "break":
        # Handle open break
        open_break = (
            db.query(BreakInterval)
            .filter(BreakInterval.session_id == ws.id, BreakInterval.end_time.is_(None))
            .order_by(BreakInterval.id.desc())
            .first()
        )
        if open_break:
            open_break.end_time = now
            db.add(open_break)

    breaks_sec = _sum_breaks(db, ws.id, as_of=now)
    ws.clock_out_time = now
    ws.total_work_seconds = _elapsed_work_seconds(ws.clock_in_time, breaks_sec, clock_out=now)
    ws.status = "ended"
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws

def session_state(db: Session, employee_id: int) -> dict:
    ws = get_active_session(db, employee_id)
    if not ws:
        return {
            "session_id": None,
            "status": "ended",
            "clock_in_time": None,
            "clock_out_time": None,
            "elapsed_work_seconds": 0,
            "elapsed_break_seconds": 0,
        }

    now = _utc_now()
    breaks_sec = _sum_breaks(db, ws.id, as_of=now)
    
    # Initialize ongoing_break_sec BEFORE the if statement
    ongoing_break_sec = 0
    if ws.status == "break":
        last_open = (
            db.query(BreakInterval)
            .filter(BreakInterval.session_id == ws.id, BreakInterval.end_time.is_(None))
            .order_by(BreakInterval.id.desc())
            .first()
        )
        if last_open:
            ongoing_break_sec = int((now - last_open.start_time).total_seconds())

    return {
        "session_id": ws.id,
        "status": ws.status,
        "clock_in_time": format_ist_datetime(ws.clock_in_time),
        "clock_out_time": format_ist_datetime(ws.clock_out_time),
        "elapsed_work_seconds": _elapsed_work_seconds(ws.clock_in_time, breaks_sec, ws.clock_out_time, now),
        "elapsed_break_seconds": ongoing_break_sec,
    }


def sessions_last_days(db: Session, employee_id: int, days: int) -> list[dict]:
    cutoff = _utc_now() - timedelta(days=days)
    rows = (
        db.query(WorkSession)
        .filter(WorkSession.employee_id == employee_id, WorkSession.clock_in_time >= cutoff)
        .order_by(WorkSession.clock_in_time.desc())
        .all()
    )
    out = []
    for s in rows:
        breaks_sec = _sum_breaks(db, s.id, as_of=_utc_now()) or 0
        total_work = (
            (s.total_work_seconds if s.status == "ended" else _elapsed_work_seconds(s.clock_in_time, breaks_sec))
            or 0
        )
        ot_sec = 0
        out.append({
            "date": format_ist_date(s.clock_in_time),
            "first_clock_in": format_ist_datetime(s.clock_in_time),
            "last_clock_out": format_ist_datetime(s.clock_out_time),
            "total_work_seconds": total_work if total_work is not None else 0,
            "total_break_seconds": breaks_sec if breaks_sec is not None else 0,
            "ot_sec": ot_sec,
        })

    return out

def get_today_completed_work(db: Session, employee_id: int) -> dict:
    """Get total completed work for today"""
    now = _utc_now()  # Use existing utility
    
    # Get today's date range in UTC (naive)
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    
    # Query completed sessions from today
    sessions = db.query(WorkSession).filter(
        WorkSession.employee_id == employee_id,
        WorkSession.status == "ended",
        WorkSession.clock_in_time >= today_start,
        WorkSession.clock_in_time < today_end
    ).all()
    
    total_work_seconds = sum(s.total_work_seconds or 0 for s in sessions)
    
    return {
        "total_work_seconds": total_work_seconds,
        "session_count": len(sessions),
        "date": today_start.date().isoformat()
    }
