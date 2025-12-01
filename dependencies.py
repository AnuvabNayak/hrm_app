from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status, APIRouter
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.orm import Session, joinedload
from db import get_db
from models import User, TokenBlacklist
from auth import decode_access_token
from schemas import UserOut
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# In-memory cache for blacklisted tokens
# Dictionary: {jti: expiry_datetime}
blacklist_cache = {}
CACHE_MAX_SIZE = 10000  # Maximum tokens to cache in memory

def _cleanup_expired_cache():
    """Remove expired tokens from memory cache"""
    global blacklist_cache
    now = datetime.now(timezone.utc)
    expired_keys = [
        jti for jti, exp_time in blacklist_cache.items()
        if exp_time < now
    ]
    for key in expired_keys:
        del blacklist_cache[key]
    
    if expired_keys:
        logger.debug(f"Cache cleanup: Removed {len(expired_keys)} expired tokens")

def is_token_blacklisted_cached(jti: str, db: Session) -> bool:
    """
    Check if token is blacklisted with in-memory caching.
    
    Strategy:
    1. Check memory cache first (instant - ~0.01ms)
    2. If not in cache, query database (first time - ~5-20ms)
    3. Cache the result for future requests (instant)
    
    Args:
        jti: JWT ID from token
        db: Database session
    
    Returns:
        True if token is blacklisted, False otherwise
    """
    # Step 1: Check memory cache
    if jti in blacklist_cache:
        exp_time = blacklist_cache[jti]
        if exp_time > datetime.now(timezone.utc):
            logger.debug(f"Cache HIT: Token {jti[:8]}... is blacklisted")
            return True  # Still blacklisted
        else:
            # Expired, remove from cache
            del blacklist_cache[jti]
            return False
    
    # Step 2: Not in cache, query database (MISS)
    try:
        blacklisted = db.query(TokenBlacklist).filter(
            TokenBlacklist.jti == jti
        ).first()
        
        # Step 3: Cache the result
        if blacklisted:
            # Add to cache with expiry time
            blacklist_cache[jti] = blacklisted.token_exp
            
            # Cleanup if cache is too large
            if len(blacklist_cache) > CACHE_MAX_SIZE:
                _cleanup_expired_cache()
            
            logger.debug(f"Cache MISS->STORE: Token {jti[:8]}... cached")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"Database error checking blacklist: {str(e)}")
        # Fail open: allow request (don't block on DB errors)
        return False

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Validate JWT token and return current user.
    
    Optimizations:
    - In-memory caching for blacklist checks
    - Better error handling & logging
    - Enhanced security checks
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        role: str = payload.get("role")
        jti: str = payload.get("jti")  # JWT ID
        
        if username is None or role is None:
            logger.warning(f"Invalid token payload: missing sub or role")
            raise credentials_exception
        
        # ✅ OPTIMIZED: Check blacklist with caching
        if jti and is_token_blacklisted_cached(jti, db):
            logger.warning(f"User {username} attempted access with blacklisted token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please login again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    except ExpiredSignatureError:
        logger.info(f"Expired token attempted: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning(f"JWT validation error: {str(e)}")
        raise credentials_exception
    
    # Fetch user with role relationship
    try:
        user = db.query(User).options(
            joinedload(User.role_rel)
        ).filter(User.username == username).first()
        
        if user is None:
            logger.warning(f"User not found: {username}")
            raise credentials_exception
        
        # Verify role matches
        if user.role_name != role:
            logger.warning(f"Role mismatch for user {username}: token={role}, db={user.role_name}")
            raise credentials_exception
        
        logger.debug(f"✅ Authentication successful: {username} ({user.role_name})")
        return user
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"User lookup error: {str(e)}")
        raise credentials_exception

def get_current_employee(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current employee from the current user"""
    from models import Employee
    
    employee = db.query(Employee).filter(
        Employee.user_id == current_user.id
    ).first()
    
    if not employee:
        logger.warning(f"Employee profile not found for user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found"
        )
    
    return employee

class RoleChecker:
    def __init__(self, allowed_roles):
        self.allowed_roles = set(allowed_roles)
    
    def __call__(self, user: User = Depends(get_current_user)):
        if user.role_name not in self.allowed_roles:
            logger.warning(f"Unauthorized access attempt: {user.username} tried to access role={self.allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )
        return True

allow_admin = RoleChecker(["admin", "super_admin"])
allow_super_admin = RoleChecker(["super_admin"])
allow_employee = RoleChecker(["employee"])
allow_manager = RoleChecker(["manager", "admin", "super_admin"])

router = APIRouter()

@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user's profile"""
    logger.debug(f"Profile requested by {current_user.username}")
    return current_user

# ✅ NEW: Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns cache and authentication statistics.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": {
            "size": len(blacklist_cache),
            "max_size": CACHE_MAX_SIZE,
            "utilization_percent": round((len(blacklist_cache) / CACHE_MAX_SIZE) * 100, 2) if CACHE_MAX_SIZE > 0 else 0
        }
    }

# from fastapi.security import OAuth2PasswordBearer
# from fastapi import Depends, HTTPException, status, APIRouter
# from jose import JWTError
# from jose.exceptions import ExpiredSignatureError
# from sqlalchemy.orm import Session, joinedload
# from db import get_db
# from models import User, TokenBlacklist
# from auth import decode_access_token
# from schemas import UserOut

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# # def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
# #     credentials_exception = HTTPException(
# #         status_code=status.HTTP_401_UNAUTHORIZED,
# #         detail="Could not validate credentials",
# #         headers={"WWW-Authenticate": "Bearer"},
# #     )
# #     try:
# #         payload = decode_access_token(token)
# #         username: str = payload.get("sub")
# #         role: str = payload.get("role")
# #         if username is None or role is None:
# #             raise credentials_exception
# #     except (ExpiredSignatureError, JWTError):
# #         raise credentials_exception

# #     user = db.query(User).filter(User.username == username).first()
# #     if user is None:
# #         raise credentials_exception
# #     user.role = role
# #     return user
# def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
#     """
#     Validate JWT token and return current user.
    
#     Now includes:
#     - Token blacklist checking (logout validation)
#     - JTI verification
#     - Enhanced error messages
#     """
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
    
#     try:
#         payload = decode_access_token(token)
#         username: str = payload.get("sub")
#         role: str = payload.get("role")
#         jti: str = payload.get("jti")  # NEW: Get JWT ID
        
#         if username is None or role is None:
#             raise credentials_exception
        
#         # Check if token is blacklisted (user logged out)
#         if jti:
#             blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
#             if blacklisted:
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Token has been revoked. Please login again.",
#                     headers={"WWW-Authenticate": "Bearer"},
#                 )
        
#     except ExpiredSignatureError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token has expired. Please login again.",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     except JWTError:
#         raise credentials_exception
#     # Fetch user with role relationship
#     user = db.query(User).options(joinedload(User.role_rel)).filter(User.username == username).first()
#     if user is None:
#         raise credentials_exception
#     # Verify role matches
#     if user.role_name != role:
#         raise credentials_exception
    
#     return user


# def get_current_employee(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get the current employee from the current user"""
#     from models import Employee  # Import here to avoid circular imports
    
#     employee = db.query(Employee).filter(Employee.user_id == current_user.id).first()
#     if not employee:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Employee profile not found"
#         )
#     return employee


# class RoleChecker:
#     def __init__(self, allowed_roles):
#         self.allowed_roles = set(allowed_roles)
#     def __call__(self, user: User = Depends(get_current_user)):
#         if user.role not in self.allowed_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Operation not permitted",
#             )
#         return True

# allow_admin = RoleChecker(["admin", "super_admin"])
# allow_super_admin = RoleChecker(["super_admin"])
# allow_employee = RoleChecker(["employee"])

# router = APIRouter()
# @router.get("/users/me", response_model=UserOut)
# def read_users_me(current_user: User = Depends(get_current_user)):
#     return current_user