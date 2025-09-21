# employees.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Employee, User
from schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut, AvatarUpdateRequest
from db import get_db
from dependencies import get_current_user, allow_admin
from typing import List

router = APIRouter(prefix="/employees", tags=["Employees"])

# ---------- Existing endpoint (keep) ----------
@router.get("/me/employee-id")
def my_employee_id(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return {"employee_id": emp.id}


# ---------- Updated endpoint ----------
@router.get("/me", response_model=EmployeeOut)
def my_employee_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    # Get username from user table
    user = db.query(User).filter(User.id == current_user.id).first()
    
    # Create response with username
    response_data = {
        "id": emp.id,
        "name": emp.name,
        "user_id": emp.user_id,
        "email": emp.email,
        "phone": emp.phone,
        "avatar_url": emp.avatar_url,
        "emp_code": emp.emp_code,
        "username": user.username if user else None
    }
    
    return response_data


# ---------- New avatar upload endpoint ----------
@router.put("/me/avatar", response_model=dict)
def update_my_avatar(
    avatar_request: AvatarUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    avatar_data = avatar_request.avatar_data.strip()
    
    # Validate base64 data URL format (if not empty)
    if avatar_data and not avatar_data.startswith('data:image/'):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    # Update avatar (empty string removes the avatar)
    emp.avatar_url = avatar_data if avatar_data else None
    db.commit()
    
    return {"message": "Avatar updated successfully"}


# ---------- Keep all other existing endpoints ----------
@router.post("/", response_model=EmployeeOut, dependencies=[Depends(allow_admin)])
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exists = db.query(Employee).filter(Employee.user_id == employee.user_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="Employee for this user already exists")
    db_employee = Employee(
        name=employee.name, 
        user_id=employee.user_id,
        email=employee.email,
        phone=employee.phone,
        avatar_url=employee.avatar_url,
        emp_code=employee.emp_code
    )
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


# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from models import Employee, User
# from schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut
# from db import get_db
# from dependencies import get_current_user, allow_admin
# from typing import List

# router = APIRouter(prefix="/employees", tags=["Employees"])

# @router.get("/me/employee-id")
# def my_employee_id(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
#     if not emp:
#         raise HTTPException(status_code=404, detail="Employee profile not found")
#     return {"employee_id": emp.id}

# @router.get("/me", response_model=EmployeeOut)
# def my_employee_profile(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)):
#     emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
#     if not emp:
#         raise HTTPException(status_code=404, detail="Employee profile not found")
#     return emp


# @router.post("/", response_model=EmployeeOut, dependencies=[Depends(allow_admin)])
# def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     exists = db.query(Employee).filter(Employee.user_id == employee.user_id).first()
#     if exists:
#         raise HTTPException(status_code=400, detail="Employee for this user already exists")
#     db_employee = Employee(
#         name=employee.name, 
#         user_id=employee.user_id,
#         email=employee.email,
#         phone=employee.phone,
#         avatar_url=employee.avatar_url,
#         emp_code=employee.emp_code
#         )
#     db.add(db_employee)
#     db.commit()
#     db.refresh(db_employee)
#     return db_employee

# @router.get("/", response_model=List[EmployeeOut], dependencies=[Depends(allow_admin)])
# def read_employees(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
#     return db.query(Employee).offset(skip).limit(limit).all()

# @router.get("/{employee_id}", response_model=EmployeeOut)
# def read_employee(employee_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
#     employee = db.query(Employee).filter(Employee.id == employee_id).first()
#     if not employee:
#         raise HTTPException(status_code=404, detail="Employee not found")

#     # Only admin/super_admin or the owner can access
#     if current_user.role not in ["admin", "super_admin"] and employee.user_id != current_user.id:
#         raise HTTPException(status_code=403, detail="Operation not permitted")
#     return employee

# @router.put("/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(allow_admin)])
# def update_employee(employee_id: int, update: EmployeeUpdate, db: Session = Depends(get_db)):
#     employee = db.query(Employee).filter(Employee.id == employee_id).first()
#     if not employee:
#         raise HTTPException(status_code=404, detail="Employee not found")
#     if update.name is not None:
#         employee.name = update.name
#     db.commit()
#     db.refresh(employee)
#     return employee

# @router.delete("/{employee_id}", dependencies=[Depends(allow_admin)])
# def delete_employee(employee_id: int, db: Session = Depends(get_db)):
#     employee = db.query(Employee).filter(Employee.id == employee_id).first()
#     if not employee:
#         raise HTTPException(status_code=404, detail="Employee not found")
#     db.delete(employee)
#     db.commit()
#     return {"detail": "Employee deleted"}