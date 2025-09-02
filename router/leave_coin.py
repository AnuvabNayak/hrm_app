from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from dependencies import get_current_user, allow_admin
from schemas import LeaveBalanceOut
from models import Employee, User
from services.leave_coins import get_available_coins

router = APIRouter(prefix="/leave-balance", tags=["Leave Balance"])

@router.get("/me", response_model=LeaveBalanceOut)
def read_my_balance(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # find employee_id for current user
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    data = get_available_coins(db, emp.id)
    return data

@router.get("/employees/{employee_id}", response_model=LeaveBalanceOut, dependencies=[Depends(allow_admin)])
def read_employee_balance(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    data = get_available_coins(db, employee_id)
    return data