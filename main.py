from fastapi import APIRouter, FastAPI, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import locale

from router.leave_types import router as leave_types_router
from router.departments import router as departments_router
from router.notifications import router as notifications_router


# ENSURE UTF-8 ENCODING AT APPLICATION LEVEL
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# SET LOCALE FOR UTF-8 (OPTIONAL)
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        pass  # Use system default

from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging

# Database imports
from db import get_db, engine, SessionLocal

# Model imports
from models import User, Employee, Base, Attendance, Role, TokenBlacklist

# Schema imports
from schemas import (
    UserCreate, 
    UserOut, 
    Token, 
    EmployeeCreate, 
    LeaveBalanceOut,
    LogoutResponse  # ← ADDED
)

# Auth imports
from auth import (
    hash_password, 
    verify_password, 
    create_access_token, 
    decode_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# Dependency imports
from dependencies import (
    get_current_user, 
    allow_admin,
    oauth2_scheme,
    blacklist_cache
)

# Router imports
from router import employees, attendance, leave, attendance_rt, inspiration, attendance_summary_routes
from router import leave_coin as leave_coins_router
from router import posts, admin_posts, roles, admin_auth, auth_password, leave
from router import location_rt
# Service imports
from services.leave_coins import grant_coins, expire_coins
from dependencies import router as dependencies_router
from services.scheduler import quote_scheduler
from services.location_websocket_service import cleanup_old_locations 

# ✅ FIXED: Define IST timezone for scheduler
from pytz import timezone as pytz_timezone
ist = pytz_timezone("Asia/Kolkata")

# Initialize scheduler
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
    # Cleanup expired token blacklist entries
    scheduler.add_job(
        cleanup_expired_blacklist,
        CronTrigger(hour=2, minute=30, timezone=ist),  # Run at 2:30 AM IST daily
        id='cleanup_token_blacklist',
        name='Clean up expired token blacklist entries',
        replace_existing=True
    )
    
    # Location cleanup job (daily at 3 AM IST) - DELETE locations > 90 days old
    def cleanup_locations_job():
        db = SessionLocal()
        try:
            cleanup_old_locations(db, retention_days=90)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Location cleanup failed: {e}")
        finally:
            db.close()

    scheduler.add_job(
        cleanup_locations_job,
        CronTrigger(hour=3, minute=0, timezone=ist),  # 3 AM IST daily
        id='location_cleanup',
        name='Clean up old location records (>90 days)',
        replace_existing=True
    )

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


def cleanup_expired_blacklist():
    """
    Remove expired tokens from blacklist table.
    
    Optimized with:
    - Batch processing (prevents long table locks)
    - Better error handling & retry logic
    - Enhanced logging
    - Cache cleanup
    
    Runs daily at 2:30 AM IST.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Count expired tokens first
        expired_count = db.query(TokenBlacklist).filter(
            TokenBlacklist.token_exp < now
        ).count()
        
        if expired_count == 0:
            logger.info("✅ Token blacklist cleanup: No expired tokens")
            return
        
        logger.info(f"🧹 Starting cleanup: {expired_count} expired tokens to remove")
        
        # ✅ NEW: Delete in batches to avoid long table locks
        batch_size = 1000
        total_deleted = 0
        
        while True:
            # Delete batch
            deleted = db.query(TokenBlacklist).filter(
                TokenBlacklist.token_exp < now
            ).limit(batch_size).delete(synchronize_session=False)
            
            if deleted == 0:
                break
            
            db.commit()
            total_deleted += deleted
            logger.debug(f"Cleanup batch: Deleted {deleted} tokens, total={total_deleted}")
        
        # ✅ NEW: Clean memory cache too
        from dependencies import _cleanup_expired_cache
        _cleanup_expired_cache()
        
        logger.info(f"✅ Cleanup complete: Removed {total_deleted} expired tokens from database and cache")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Cleanup error: {str(e)}")
        
        # ✅ NEW: Retry logic
        try:
            logger.info("🔄 Attempting retry...")
            db.close()
            db = SessionLocal()
            
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            deleted = db.query(TokenBlacklist).filter(
                TokenBlacklist.token_exp < now
            ).delete()
            db.commit()
            
            logger.info(f"✅ Retry succeeded: Deleted {deleted} tokens")
        except Exception as retry_error:
            logger.error(f"❌ Retry failed: {str(retry_error)}")
            db.rollback()
    
    finally:
        db.close()


# ENHANCED FASTAPI CONFIGURATION
app = FastAPI(
    title="Zytexa HRM API", 
    version="1.0.0", 
    lifespan=lifespan
)

from dotenv import load_dotenv
load_dotenv()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# ENHANCED CORS WITH UTF-8 SUPPORT
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # ENSURE UTF-8 HEADERS ARE EXPOSED
    expose_headers=["Content-Type", "Content-Encoding"],
)

# ADD UTF-8 RESPONSE MIDDLEWARE
@app.middleware("http")
async def add_utf8_header(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


# app = FastAPI(title="Zytexa HRM API", version="1.0.0", lifespan=lifespan)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],
#     allow_credentials=True,# Set to False unless you need credentialed cross-origin requests (cookies, HTTP auth)
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
    
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
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role_name},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)                    
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "expires_in": 3 * 24 * 60 * 60,  # 3 days in seconds (259200)
        "username": user.username,
        "role": user.role_name
    }

@app.post("/logout", response_model=LogoutResponse)
async def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logout user by blacklisting their current JWT token.
    
    Optimized with:
    - Immediate cache invalidation
    - Better error handling
    - Enhanced logging
    """
    try:
        # Decode token to get jti and expiry
        payload = decode_access_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if not jti:
            logger.warning(f"Logout attempt without JTI: {current_user.username}")
            raise HTTPException(
                status_code=400,
                detail="Token does not contain required tracking ID"
            )
        
        # Check if already blacklisted
        existing = db.query(TokenBlacklist).filter(
            TokenBlacklist.jti == jti
        ).first()
        
        if existing:
            logger.info(f"User {current_user.username} attempted logout but already logged out")
            return LogoutResponse(
                message="Already logged out",
                success=True,
                username=current_user.username
            )
        
        # Convert expiry timestamp to datetime
        token_exp = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
        
        # Add to blacklist table
        blacklist_entry = TokenBlacklist(
            jti=jti,
            user_id=current_user.id,
            username=current_user.username,
            token_exp=token_exp,
            reason="user_logout"
        )
        db.add(blacklist_entry)
        db.commit()
        
        # ✅ NEW: Immediately add to cache
        blacklist_cache[jti] = token_exp
        
        logger.info(f"✅ User {current_user.username} logged out successfully")
        
        return LogoutResponse(
            message="Logged out successfully",
            success=True,
            username=current_user.username
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Logout failed for {current_user.username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}"
        )

# Routers
app.include_router(router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(leave.router)
app.include_router(leave_coins_router.router)
app.include_router(dependencies_router)
app.include_router(attendance_rt.router)
app.include_router(inspiration.router)
app.include_router(posts.router)
app.include_router(admin_posts.router)
app.include_router(roles.router)
app.include_router(admin_auth.router)
app.include_router(attendance_summary_routes.router)
app.include_router(auth_password.router)
app.include_router(leave.router)
# NEW: Leave management routers 
app.include_router(leave_types_router)
app.include_router(departments_router)
app.include_router(notifications_router)
app.include_router(location_rt.router)


@app.post("/register", response_model=UserOut)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    User registration endpoint with FIXED role handling.
    
    NOW SYNCS BOTH:
    - role_id (foreign key to roles table) ✅
    - role (legacy column for backward compatibility) ✅
    
    This fixes the bug where new admin/manager users couldn't login.
    """
    
    # ============================================================================
    # STEP 1: Check if username exists
    # ============================================================================
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # ============================================================================
    # STEP 2: Get role from roles table
    # ============================================================================
    from models import Role
    role_obj = db.query(Role).filter(Role.name == user.role).first()
    
    if not role_obj:
        # Default to employee if role not found or invalid
        role_obj = db.query(Role).filter(Role.name == "employee").first()
        if not role_obj:
            raise HTTPException(
                status_code=500, 
                detail="System roles not configured. Please contact administrator."
            )
    
    # ============================================================================
    # STEP 3: Hash password
    # ============================================================================
    from auth import hash_password
    hashed_pw = hash_password(user.password)
    
    # ============================================================================
    # STEP 4: CREATE USER WITH BOTH COLUMNS SYNCED (THE FIX!) ✅
    # ============================================================================
    db_user = User(
        username=user.username,
        hashedpassword=hashed_pw,
        email=user.email,
        role_id=role_obj.id,           # ✅ NEW: Foreign key to roles table
        role=role_obj.name,             # ✅ FIX: Sync legacy column!
        phone=user.phone,
        avatar_url=user.avatar_url,
        emp_code=user.emp_code
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # ============================================================================
    # STEP 5: Auto-create employee profile
    # ============================================================================
    from models import Employee
    db_employee = Employee(
        user_id=db_user.id,
        name=user.username,
        email=user.email,
        phone=user.phone,
        avatar_url=user.avatar_url,
        emp_code=user.emp_code
    )
    
    db.add(db_employee)
    db.commit()
    
    return db_user


# @app.post("/register", response_model=UserOut)
# async def register_user(user: UserCreate, db: Session = Depends(get_db)):
#     """
#     User registration endpoint.
    
#     **Changes:**
#     - Now requires email at registration
#     - Email stored in both users and employees tables
#     - Users.email = authentication email
#     - Employees.email = work email (can be same or different)
#     """
    
#     # Check if username exists
#     existing_user = db.query(User).filter(User.username == user.username).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Username already registered")
    
#     # ✅ NEW: Check if email exists
#     existing_email = db.query(User).filter(User.email == user.email).first()
#     if existing_email:
#         raise HTTPException(status_code=400, detail="Email already registered")
    
#     # Get role_id from roles table
#     from models import Role
#     role_obj = db.query(Role).filter(Role.name == user.role).first()
    
#     if not role_obj:
#         # Default to employee if role not found
#         role_obj = db.query(Role).filter(Role.name == "employee").first()
#         if not role_obj:
#             raise HTTPException(
#                 status_code=500,
#                 detail="System roles not configured. Please contact administrator."
#             )
    
#     # Create user with email
#     hashed_pw = hash_password(user.password)
#     db_user = User(
#         username=user.username,
#         hashedpassword=hashed_pw,
#         role_id=role_obj.id,        # New foreign key
#         role=role_obj.name,          # Sync column
#         email=user.email,
#         phone=user.phone,
#         avatar_url=user.avatar_url,
#         emp_code=user.emp_code
#     )
#     # db_user = User(
#     #     username=user.username,
#     #     email=user.email,  # ✅ NEW: Store email in users table
#     #     hashed_password=hashed_pw,
#     #     role_id=role_obj.id,
#     #     role=role_obj.name
#     # )
    
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
    
#     # ONLY create employee for appropriate roles
#     if role_obj.name in ["employee", "manager"]:
#         db_employee = Employee(
#             user_id=db_user.id,
#             name=user.username,
#             email=user.email,
#             phone=user.phone,
#             avatar_url=user.avatar_url,
#             emp_code=user.emp_code,
#             is_manager=(role_obj.name == "manager")
#         )
#         db.add(db_employee)
#         db.commit()
#     return db_user
    
#     # # Auto-create employee profile
#     # db_employee = Employee(
#     #     user_id=db_user.id,
#     #     name=user.username,
#     #     email=user.email,  # Same email by default (can be changed later)
#     #     phone=user.phone,
#     #     avatar_url=user.avatar_url,
#     #     emp_code=user.emp_code
#     # )
    
#     # db.add(db_employee)
#     # db.commit()
    
#     # return db_user


# OLD registration endpoint commented out for reference


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

# Add this admin user/employee creation endpoint in main.py

@app.post("/admin/create-user-employee", dependencies=[Depends(allow_admin)])
def admin_create_user_employee(
    user_data: UserCreate,
    employee_data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin endpoint to create a User and Employee in a single transaction.
    
    ALSO FIXED to sync both role columns.
    """
    
    # ============================================================================
    # STEP 1: Check if username already exists
    # ============================================================================
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # ============================================================================
    # STEP 2: Check if email already exists in employees if provided
    # ============================================================================
    if employee_data.email:
        existing_email = db.query(Employee).filter(
            Employee.email == employee_data.email
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    try:
        # ====================================================================
        # STEP 3: Get role from roles table
        # ====================================================================
        from models import Role
        role_obj = db.query(Role).filter(Role.name == user_data.role).first()
        
        if not role_obj:
            raise HTTPException(
                status_code=400, 
                detail=f"Role '{user_data.role}' not found. Valid roles: employee, manager, admin, super_admin"
            )
        
        # ====================================================================
        # STEP 4: Hash password
        # ====================================================================
        from auth import hash_password
        hashed_password = hash_password(user_data.password)
        
        # ====================================================================
        # STEP 5: Create user with BOTH COLUMNS SYNCED (THE FIX!) ✅
        # ====================================================================
        db_user = User(
            username=user_data.username,
            hashedpassword=hashed_password,
            email=user_data.email,
            role_id=role_obj.id,           # ✅ NEW: Foreign key
            role=role_obj.name,             # ✅ FIX: Sync!
            phone=user_data.phone,
            avatar_url=user_data.avatar_url,
            emp_code=user_data.emp_code
        )
        
        db.add(db_user)
        db.flush()  # Get the user ID without committing
        
        # ====================================================================
        # STEP 6: Create employee profile
        # ====================================================================
        from models import Employee
        db_employee = Employee(
            user_id=db_user.id,
            name=employee_data.name,
            email=employee_data.email,
            phone=employee_data.phone,
            avatar_url=employee_data.avatar_url,
            emp_code=employee_data.emp_code,
            department_id=employee_data.department_id,
            manager_id=employee_data.manager_id,
            employment_type=employee_data.employment_type,
            is_manager=employee_data.is_manager,
            is_leave_eligible=employee_data.is_leave_eligible
        )
        
        db.add(db_employee)
        db.commit()
        
        return {
            "id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "email": db_user.email,
            "message": f"User {db_user.username} created successfully with role: {db_user.role}"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"User creation failed: {str(e)}"
        )



# @app.post("/admin/create-user-employee", dependencies=[Depends(allow_admin)])
# def admin_create_user_employee(
#     user_data: UserCreate,
#     employee_data: EmployeeCreate,
#     db: Session = Depends(get_db)
# ):
#     """
#     Admin endpoint to create a User and Employee in a single transaction
#     """
#     # Check if username already exists
#     existing_user = db.query(User).filter(User.username == user_data.username).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Username already exists")
    
#     # Check if email already exists in employees (if provided)
#     if employee_data.email:
#         existing_email = db.query(Employee).filter(Employee.email == employee_data.email).first()
#         if existing_email:
#             raise HTTPException(status_code=400, detail="Email already exists")
    
#     try:
#         # Get role from roles table
#         role_obj = db.query(Role).filter(Role.name == user_data.role).first()
#         if not role_obj:
#             raise HTTPException(status_code=400, detail=f"Role '{user_data.role}' not found")
#         # Create user first
#         hashed_password = hash_password(user_data.password)
        
#         db_user = User(
#             username=user_data.username,
#             hashedpassword=hashed_password,
#             email=user_data.email,
#             role_id=role_obj.id,        # New
#             role=role_obj.name,          # Sync
#             phone=user_data.phone,
#             avatar_url=user_data.avatar_url,
#             emp_code=user_data.emp_code
#         )
#         # db_user = User(
#         #     username=user_data.username,
#         #     hashed_password=hashed_password,
#         #     role=user_data.role,
#         # )
#         db.add(db_user)
#         db.flush()  # Get the user ID without committing
        
#         # Create employee linked to the user
#         db_employee = Employee(
#             name=employee_data.name,
#             user_id=db_user.id,
#             email=employee_data.email,
#             phone=employee_data.phone,
#             avatar_url=employee_data.avatar_url,
#             emp_code=employee_data.emp_code,
#         )
#         db.add(db_employee)
#         db.commit()
        
#         return {
#             "message": "User and employee created successfully",
#             "user_id": db_user.id,
#             "employee_id": db_employee.id,
#             "username": db_user.username,
#             "employee_name": db_employee.name,
#         }
    
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Failed to create user and employee: {str(e)}")

@app.get("/leave-balance/me", response_model=LeaveBalanceOut)
def get_leave_balance_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get current user's leave balance"""
    from services.leave_coins import get_available_coins
    
    # Get employee profile
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    # Get balance data
    balance_data = get_available_coins(db, emp.id)
    return LeaveBalanceOut(**balance_data)


Base.metadata.create_all(bind=engine) # TODO
        
# uvicorn main:app --reload
# http://127.0.0.1:8000/docs
# for tests run: python -m pytest -q
