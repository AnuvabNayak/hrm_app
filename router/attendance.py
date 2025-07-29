from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Attendance, Employee
from schemas import AttendanceCreate, AttendanceUpdate, AttendanceOut
from dependencies import get_db, get_current_user, allow_employee
from typing import List
import pytz
from utils import to_ist
from datetime import timezone

IST = pytz.timezone("Asia/Kolkata")

router = APIRouter(prefix="/attendance", tags=["Attendance"])

@router.post("/attendance/log", dependencies=[Depends(allow_employee)])
def log_attendance(attendance: AttendanceCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Only employees can log their own attendance
    employee = db.query(Employee).filter(Employee.id == attendance.employee_id).first()
    if not employee or employee.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Operation not permitted")

    # Calculate work_hours if both times are provided
    work_hours = None
    if attendance.login_time and attendance.logout_time:
        delta = attendance.logout_time - attendance.login_time
        work_hours = float(round(delta.total_seconds() / 3600, 2))
    
    db_attendance = Attendance(
        employee_id=attendance.employee_id,
        login_time=attendance.login_time,
        logout_time=attendance.logout_time,
        on_leave=attendance.on_leave,
        work_hours=work_hours
    )
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance

@router.get("/", response_model=List[AttendanceOut])
def read_attendance(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    records = db.query(Attendance).offset(skip).limit(limit).all()
    for record in records:
        record.login_time = to_ist(record.login_time)
        record.logout_time = to_ist(record.logout_time)
    return records

@router.get("/{attendance_id}", response_model=AttendanceOut)
def read_attendance_record(attendance_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance: ...
    attendance.login_time = to_ist(attendance.login_time)
    attendance.logout_time = to_ist(attendance.logout_time)
    return attendance

# @router.get("/", response_model=List[AttendanceOut])
# def read_attendance(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     # Get a list of attendance records.
#     return db.query(Attendance).offset(skip).limit(limit).all()

# @router.get("/{attendance_id}", response_model=AttendanceOut)
# def read_attendance_record(attendance_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
#     if not attendance:
#         raise HTTPException(status_code=404, detail="Attendance record not found")
#     employee = db.query(Employee).filter(Employee.id == attendance.employee_id).first()
#     if current_user.role not in ["admin", "super_admin"] and (not employee or employee.user_id != current_user.id):
#         raise HTTPException(status_code=403, detail="Operation not permitted")
#     return attendance

@router.put("/{attendance_id}", response_model=AttendanceOut)
def update_attendance(attendance_id: int, update: AttendanceUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    for field, value in update.model_dump (exclude_unset=True).items():
        setattr(attendance, field, value)
    # Use float with rounding for accurate work hours
    if attendance.login_time and attendance.logout_time:
        delta = attendance.logout_time - attendance.login_time
        attendance.work_hours = round(delta.total_seconds() / 3600, 2)
    db.commit()
    db.refresh(attendance)
    return attendance

@router.delete("/{attendance_id}")
def delete_attendance(attendance_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Delete an attendance record.
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    db.delete(attendance)
    db.commit()
    return {"detail": "Attendance record deleted"}