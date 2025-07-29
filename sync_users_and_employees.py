from models import User, Employee
from db import SessionLocal

db = SessionLocal()
employee_users = db.query(User).filter(User.role == "employee").all()
created = 0
for user in employee_users:
    if not db.query(Employee).filter(Employee.user_id == user.id).first():
        employee = Employee(name=user.username, user_id=user.id)
        db.add(employee)
        created += 1
db.commit()
db.close()
print(f"Created {created} missing Employee records linked to Users.")