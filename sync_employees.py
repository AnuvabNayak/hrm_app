from models import User, Employee
from db import SessionLocal

db = SessionLocal()
employee_users = db.query(User).filter(User.role == "employee").all()
for user in employee_users:
    if not db.query(Employee).filter(Employee.user_id == user.id).first():
        employee = Employee(name=user.username, user_id=user.id)
        db.add(employee)
db.commit()
db.close()
print("Employee synchronization completed.")