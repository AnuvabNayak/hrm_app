from db import SessionLocal
from models import User, Employee
from auth import hash_password

db = SessionLocal()

try:
    # Check if admin exists
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Admin user already exists")
        print(f"Username: admin")
    else:
        # Create admin user
        admin_user = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            role="super_admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        # Create admin employee profile
        admin_emp = Employee(
            name="System Administrator",
            user_id=admin_user.id,
            email="admin@company.com",
            emp_code="EMP001"
        )
        db.add(admin_emp)
        db.commit()
        
        print("Admin user created successfully!")
        print(f"Username: admin")
        print(f"Password: admin123")
        print("Change password after first login!")
        
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
