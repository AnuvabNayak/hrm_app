from fastapi import APIRouter, FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from db import get_db, engine, SessionLocal
from models import User, Employee, Base, Attendance
from schemas import UserCreate, UserOut, Token
from auth import hash_password, verify_password, create_access_token
from dependencies import get_current_user
from router import employees, attendance, leave
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler

router = APIRouter()

@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Authenticate user and return JWT token.
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="User is not registered")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# Protect Endpoints with Role Checks

app = FastAPI()

app.include_router(router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(leave.router)

@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = hash_password(user.password)
    new_user = User(username=user.username, hashed_password=hashed_pw, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # If regular employee, create associated Employee record!
    if new_user.role == "employee":
        if not db.query(Employee).filter(Employee.user_id == new_user.id).first():
            employee = Employee(name=new_user.username, user_id=new_user.id)
            db.add(employee)
            db.commit()
    return new_user

@app.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    # Get the current authenticated user.
    return current_user

Base.metadata.create_all(bind=engine)

def remove_old_attendance():
    db = SessionLocal()
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    db.query(Attendance).filter(Attendance.login_time < threshold).delete()
    db.commit()
    db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(remove_old_attendance, "interval", days=1)
scheduler.start()


# uvicorn main:app --reload
# http://127.0.0.1:8000/docs









# @app.post("/token", response_model=Token)
# def login_for_access_token(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db)
# ):
#     user = db.query(User).filter(User.username == form_data.username).first()
#     if not user or not verify_password(form_data.password, user.hashed_password):
#         raise HTTPException(status_code=401, detail="Incorrect username or password")
#     access_token = create_access_token(data={"sub": user.username, "role": user.role})
#     return {"access_token": access_token, "token_type": "bearer"}


# @app.get("/test-db-connection")
# def test_db_connection():
#     try:
#         db = SessionLocal()
#         db.execute(text("SELECT 1"))  #connection testing
#         db.close()
#         return {"status": "success", "message": "Database connection successful"}
#     except SQLAlchemyError as e:
#         return {"status": "error", "message": f"Database connection failed: {str(e)}"}