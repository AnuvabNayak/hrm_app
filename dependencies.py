from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status, APIRouter
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.orm import Session
from db import get_db
from models import User
from auth import decode_access_token
from schemas import UserOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
    except (ExpiredSignatureError, JWTError):
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    user.role = role
    return user


def get_current_employee(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current employee from the current user"""
    from models import Employee  # Import here to avoid circular imports
    
    employee = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found"
        )
    return employee


class RoleChecker:
    def __init__(self, allowed_roles):
        self.allowed_roles = set(allowed_roles)
    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )
        return True

allow_admin = RoleChecker(["admin", "super_admin"])
allow_super_admin = RoleChecker(["super_admin"])
allow_employee = RoleChecker(["employee"])

router = APIRouter()
@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# latest:
# from fastapi.security import OAuth2PasswordBearer
# from fastapi import Depends, HTTPException, status, APIRouter
# from jose import JWTError, ExpiredSignatureError
# from sqlalchemy.orm import Session
# from db import get_db
# from models import User
# from auth import decode_access_token
# from schemas import UserOut

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )

#     try:
#         payload = decode_access_token(token)
#         username: str = payload.get("sub")
#         role: str = payload.get("role")
#         if username is None or role is None:
#             raise credentials_exception
#     except (ExpiredSignatureError, JWTError):
#         raise credentials_exception

#     user = db.query(User).filter(User.username == username).first()
#     if user is None:
#         raise credentials_exception

#     # Attach role from token for this request scope
#     user.role = role
#     return user

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

# oldest:
# from fastapi.security import OAuth2PasswordBearer
# from fastapi import Depends, HTTPException, status, APIRouter
# from jose import JWTError
# from sqlalchemy.orm import Session

# from db import get_db
# from models import User
# from auth import decode_access_token
# from schemas import UserOut

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = decode_access_token(token)
#         username: str = payload.get("sub")
#         role: str = payload.get("role")
#         if username is None or role is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception

#     user = db.query(User).filter(User.username == username).first()
#     if user is None:
#         raise credentials_exception

#     # Attach role from token (authoritative source)
#     user.role = role
#     return user

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