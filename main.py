from fastapi import APIRouter, FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging

from db import get_db, engine, SessionLocal
from models import User, Employee, Base, Attendance
from schemas import UserCreate, UserOut, Token
from auth import hash_password, verify_password, create_access_token
from dependencies import get_current_user
from router import employees, attendance, leave, attendance_rt, inspiration
from router import leave_coin as leave_coins_router
from services.leave_coins import grant_coins, expire_coins
from dependencies import router as dependencies_router
from services.scheduler import quote_scheduler

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

def remove_old_attendance():
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        db.query(Attendance).filter(Attendance.login_time < threshold).delete()
        db.commit()
    finally:
        db.close()

def grant_monthly_coins():
    db = SessionLocal()
    try:
        employees = db.query(Employee).all()
        total_granted = 0
        for e in employees:
            total_granted += grant_coins(db, e.id, amount=1, source="monthly_grant")
        db.commit()
        logging.getLogger("scheduler").info(f"Monthly grant done. total_granted={total_granted}")
    except Exception as ex:
        db.rollback()
        logging.getLogger("scheduler").exception("Monthly grant failed: %s", ex)
    finally:
        db.close()

def expire_old_coins():
    db = SessionLocal()
    try:
        total = expire_coins(db)
        db.commit()
        logging.getLogger("scheduler").info(f"Expired coins run done. total_expired={total}")
    except Exception as ex:
        db.rollback()
        logging.getLogger("scheduler").exception("Expire coins failed: %s", ex)
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    scheduler.add_job(remove_old_attendance, "interval", days=1)
    scheduler.add_job(grant_monthly_coins, CronTrigger(day="1", hour=0, minute=0))
    scheduler.add_job(expire_old_coins, "interval", days=1)
       
    # daily quote featch
    def fetch_daily_quote_job():
        db = SessionLocal()
        try:
            from services.quotes import fetch_and_store_quote
            fetch_and_store_quote(db)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    # This runs 5 minutes after 00:00 IST daily 
    scheduler.add_job(fetch_daily_quote_job, CronTrigger(hour=0, minute=5))
    
    scheduler.start()
    try:
        yield
    finally:
        # shutdown
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app = FastAPI(title="Zytexa HRM API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,# Set to False unless you need credentialed cross-origin requests (cookies, HTTP auth)
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
async def startup_event():
    """Start background services"""
    print("Starting Zytexa HRM API...")
    quote_scheduler.start()
    print("All background services started")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services"""
    print("Shutting down Zytexa HRM API...")
    quote_scheduler.stop()
    print("All background services stopped")
    
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

# Routers
app.include_router(router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(leave.router)
app.include_router(leave_coins_router.router)
app.include_router(dependencies_router)
app.include_router(attendance_rt.router)
app.include_router(inspiration.router)

@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    role = "employee"
    hashed_pw = hash_password(user.password)
    new_user = User(username=user.username, hashed_password=hashed_pw, role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # If regular employee, create associated Employee record!
    if role == "employee":
        if not db.query(Employee).filter(Employee.user_id == new_user.id).first():
            employee = Employee(
                name=new_user.username, 
                user_id=new_user.id,
                email=user.email,
                phone=user.phone,
                avatar_url=user.avatar_url,
                emp_code=user.emp_code
                )
            db.add(employee)
            db.commit()
            db.refresh(employee)
    return new_user


@app.post("/__dev__/grant-now")
def dev_grant_now(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Not permitted")
    from models import Employee
    from services.leave_coins import grant_coins
    total = 0
    for e in db.query(Employee).all():
        total += grant_coins(db, e.id, 1, "manual_dev_grant")
    db.commit()
    return {"granted": total}

@app.post("/__dev__/expire-now")
def dev_expire_now(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Not permitted")
    from services.leave_coins import expire_coins
    total = expire_coins(db)
    db.commit()
    return {"expired": total}


Base.metadata.create_all(bind=engine) # TODO
        
# uvicorn main:app --reload
# http://127.0.0.1:8000/docs
# for tests run: python -m pytest -q

# @app.get("/test-db-connection")
# def test_db_connection():
#     try:
#         db = SessionLocal()
#         db.execute(text("SELECT 1"))  #connection testing
#         db.close()
#         return {"status": "success", "message": "Database connection successful"}
#     except SQLAlchemyError as e:
#         return {"status": "error", "message": f"Database connection failed: {str(e)}"}

    # if new_user.role == "employee":
    #     if not db.query(Employee).filter(Employee.user_id == new_user.id).first():
    #         employee = Employee(name=new_user.username, user_id=new_user.id)
    #         db.add(employee)
    #         db.commit()
    # return new_user