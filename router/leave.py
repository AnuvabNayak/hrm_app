from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from models import LeaveRequest, Employee
from schemas import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestOut
from dependencies import get_db, get_current_user, allow_admin
from typing import List
from utils import to_ist

router = APIRouter(prefix="/leaves", tags=["leaves"])

@router.post("/", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def create_leave(leave: LeaveRequestCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if not employee or (current_user.role not in ["admin", "super_admin"] and employee.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Operation not permitted")
    db_leave = LeaveRequest(**leave.model_dump()) #model_dump
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)
    return db_leave

@router.post("/{leave_id}/approve", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
def approve_leave(leave_id: int = Path(...), db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status == "approved":
        raise HTTPException(status_code=400, detail="Leave already approved")
    leave.status = "approved"
    db.commit()
    db.refresh(leave)
    return leave

@router.post("/{leave_id}/deny", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
def deny_leave(leave_id: int = Path(...), db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status == "denied":
        raise HTTPException(status_code=400, detail="Leave already denied")
    leave.status = "denied"
    db.commit()
    db.refresh(leave)
    return leave

@router.get("/", response_model=List[LeaveRequestOut])
def read_leaves(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leaves = db.query(LeaveRequest).offset(skip).limit(limit).all()
    for leave in leaves:
        leave.start_date = to_ist(leave.start_date)
        leave.end_date = to_ist(leave.end_date)
    return leaves

@router.get("/{leave_id}", response_model=LeaveRequestOut)
def read_leave(leave_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    # Ownership and RBAC checks here (existing)
    leave.start_date = to_ist(leave.start_date)
    leave.end_date = to_ist(leave.end_date)
    return leave

@router.put("/{leave_id}", response_model=LeaveRequestOut)
def update_leave(leave_id: int, update: LeaveRequestUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if current_user.role not in ["admin", "super_admin"] and (not employee or employee.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Operation not permitted")

    for field, value in update.dict(exclude_unset=True).items():
        # Employees cannot change status!
        if field == "status" and current_user.role not in ["admin", "super_admin"]:
            continue  # or raise HTTPException(status_code=403, detail="Only admin can change status.")
        setattr(leave, field, value)
    db.commit()
    db.refresh(leave)
    return leave

@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave(leave_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if current_user.role not in ["admin", "super_admin"] and (not employee or employee.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Operation not permitted")
    db.delete(leave)
    db.commit()
    return
