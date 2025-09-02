from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Employee
from schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut
from db import get_db
from dependencies import get_current_user, allow_admin
from typing import List

router = APIRouter(prefix="/employees", tags=["Employees"])

@router.post("/", response_model=EmployeeOut, dependencies=[Depends(allow_admin)])
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Admin creates employee for a given user_id only if your schema supports it.
    # For now, bind to current admin if needed (adjust as per your domain).
    db_employee = Employee(name=employee.name, user_id=current_user.id)
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.get("/", response_model=List[EmployeeOut], dependencies=[Depends(allow_admin)])
def read_employees(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return db.query(Employee).offset(skip).limit(limit).all()

@router.get("/{employee_id}", response_model=EmployeeOut)
def read_employee(employee_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Only admin/super_admin or the owner can access
    if current_user.role not in ["admin", "super_admin"] and employee.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Operation not permitted")
    return employee

@router.put("/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(allow_admin)])
def update_employee(employee_id: int, update: EmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if update.name is not None:
        employee.name = update.name
    db.commit()
    db.refresh(employee)
    return employee

@router.delete("/{employee_id}", dependencies=[Depends(allow_admin)])
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(employee)
    db.commit()
    return {"detail": "Employee deleted"}