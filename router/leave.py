from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from models import LeaveRequest, Employee
from schemas import LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestOut
from db import get_db
from dependencies import get_current_user, allow_admin
from typing import List

router = APIRouter(prefix="/leaves", tags=["Leaves"])

@router.post("/", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def create_leave(leave: LeaveRequestCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if not employee or (current_user.role not in ["admin", "super_admin"] and employee.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Operation not permitted")
    db_leave = LeaveRequest(**leave.model_dump())
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)
    return db_leave

@router.post("/{leave_id}/approve", response_model=LeaveRequestOut, dependencies=[Depends(allow_admin)])
def approve_leave(leave_id: int = Path(...), db: Session = Depends(get_db)):
    from services.leave_coins import consume_coins

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave.status == "approved":
        raise HTTPException(status_code=400, detail="Leave already approved")

    # Validate dates
    if leave.end_date < leave.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

    # Calculate days (inclusive)
    start_date = leave.start_date.date()
    end_date = leave.end_date.date()
    days = (end_date - start_date).days + 1
    if days <= 0:
        raise HTTPException(status_code=400, detail="Invalid leave duration")

    # Attempt to consume coins
    consumed = consume_coins(db, leave.employee_id, amount=days, ref_leave_request_id=leave.id)
    if consumed < days:
        db.rollback()
        raise HTTPException(status_code=400, detail="Insufficient leave balance")

    # Set approved
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
    query = db.query(LeaveRequest)
    if current_user.role not in ["admin", "super_admin"]:
        query = query.join(Employee).filter(Employee.user_id == current_user.id)
    return query.offset(skip).limit(limit).all()

@router.get("/{leave_id}", response_model=LeaveRequestOut)
def read_leave(leave_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    if current_user.role not in ["admin", "super_admin"] and (not employee or employee.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Operation not permitted")
    return leave

@router.put("/{leave_id}", response_model=LeaveRequestOut)
def update_leave(leave_id: int, update: LeaveRequestUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    # Employees cannot update leave once submitted; only admins can modify
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Employees cannot update leave once submitted")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(leave, field, value)
    db.commit()
    db.refresh(leave)
    return leave

@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
def delete_leave(leave_id: int, db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    db.delete(leave)
    db.commit()