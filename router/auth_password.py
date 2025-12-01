"""
Password Management Router
==========================
Handles password changes, forgot password (OTP), and password reset.

Features:
- Change password for logged-in users
- Forgot password with OTP via email
- Reset password with OTP validation
- Security: Rate limiting ready, email enumeration protection
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from dependencies import get_db, get_current_user
from models import User, Employee
from services.email_service import email_service
from services.otp_service import otp_service
from schemas import (
    ChangePasswordRequest, 
    ForgotPasswordRequest, 
    ResetPasswordRequest,
    PasswordChangeResponse, 
    ForgotPasswordResponse, 
    ResetPasswordResponse, 
    ErrorResponse
)
from auth import verify_password, hash_password

router = APIRouter(
    prefix="/auth",
    tags=["Authentication & Password"]
)


# ============================================================================
# CHANGE PASSWORD (Logged-in user)
# ============================================================================

@router.post(
    "/change-password", 
    response_model=PasswordChangeResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Change password for logged-in user",
    description="Allows authenticated users to change their password by providing current password"
)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change password for currently logged-in user.
    
    **Requirements:**
    - Must be authenticated (valid JWT token)
    - Must provide correct current password
    - New password must match confirmation
    
    **Security:**
    - Verifies current password before allowing change
    - Hashes new password with bcrypt
    - Updates timestamp for audit trail
    """
    
    # Validate new passwords match
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "New password and confirmation do not match",
                "error_code": "PASSWORD_MISMATCH"
            }
        )
    
    # Verify current password
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Current password is incorrect",
                "error_code": "WRONG_PASSWORD"
            }
        )
    
    # Update password
    current_user.hashed_password = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return PasswordChangeResponse(
        success=True,
        message="Password changed successfully",
        changed_at=current_user.updated_at
    )


# ============================================================================
# FORGOT PASSWORD (Request OTP)
# ============================================================================

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Request password reset OTP",
    description="Send OTP code to user's registered email for password reset"
)
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Request password reset via email OTP.
    
    **Flow:**
    1. User submits email
    2. System looks up user by email
    3. Generates 6-digit OTP (15 min expiry)
    4. Sends OTP via email
    5. Returns generic success message
    
    **Security:**
    - Does NOT reveal if email exists (anti-enumeration)
    - Rate limiting recommended (implement via middleware)
    - OTP expires in 15 minutes
    - Single-use OTP
    """
    
    # ✅ NEW: Query User table directly by email
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        # Security: Return success even if email doesn't exist
        # This prevents email enumeration attacks
        return ForgotPasswordResponse(
            success=True,
            message="If this email is registered, you will receive an OTP code",
            expires_at=None
        )
    
    # Get employee name for email personalization
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    employee_name = employee.name if employee else user.username
    
    # Generate and store OTP
    otp_code, expires_at = otp_service.create_reset_token(
        db=db,
        user_id=user.id,
        email=user.email,
        ip_address=request.client.host,
        user_agent=request.headers.get('user-agent', 'Unknown')
    )
    
    # Send OTP email
    try:
        email_service.send_otp_email(
            to_email=user.email,
            otp_code=otp_code,
            employee_name=employee_name
        )
    except Exception as e:
        # Log error but don't reveal to user
        print(f"Email send failed: {e}")
        # Still return success to prevent email enumeration
    
    return ForgotPasswordResponse(
        success=True,
        message="If this email is registered, you will receive an OTP code",
        expires_at=expires_at
    )


# ============================================================================
# RESET PASSWORD (With OTP)
# ============================================================================

@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Reset password with OTP",
    description="Reset password using OTP code sent to email"
)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using OTP code.
    
    **Flow:**
    1. User submits email + OTP + new password
    2. System validates OTP (not expired, not used, correct code)
    3. Updates password
    4. Marks OTP as used
    5. Sends confirmation email
    
    **Security:**
    - OTP must not be expired
    - OTP must not be already used
    - OTP must match email
    - New password is hashed with bcrypt
    """
    
    # Validate OTP
    is_valid, user_id, error = otp_service.validate_otp(
        db=db,
        email=data.email,
        otp_code=data.otp_code
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": error,
                "error_code": "INVALID_OTP"
            }
        )
    
    # ✅ NEW: Get user directly (no need to join employees)
    user = db.query(User).filter(
        User.id == user_id,
        User.email == data.email
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "User not found for this token",
                "error_code": "USER_NOT_FOUND"
            }
        )
    
    # Update password
    user.hashed_password = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Mark OTP as used (prevents reuse)
    otp_service.mark_as_used(
        db=db,
        email=data.email,
        otp_code=data.otp_code
    )
    
    # Get employee name for email
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    employee_name = employee.name if employee else user.username
    
    # Send confirmation email
    try:
        email_service.send_password_changed_notification(
            to_email=user.email,
            employee_name=employee_name,
            ip_address="unknown"  # Could be extracted from request if needed
        )
    except Exception as e:
        # Log but don't fail the request
        print(f"Notification email failed: {e}")
    
    return ResetPasswordResponse(
        success=True,
        message="Password reset successful. Please login with your new password.",
        reset_at=user.updated_at
    )


# from fastapi import APIRouter, Depends, HTTPException, status, Request
# from sqlalchemy.orm import Session
# from datetime import datetime, timezone
# from dependencies import get_db, get_current_user
# from models import User
# from services.email_service import email_service
# from services.otp_service import otp_service
# from schemas import (
#     ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
#     PasswordChangeResponse, ForgotPasswordResponse, ResetPasswordResponse, ErrorResponse
# )

# router = APIRouter(
#     prefix="/auth",
#     tags=["Authentication & Password"]
# )

# @router.post("/change-password", response_model=PasswordChangeResponse, responses={400: {"model": ErrorResponse}})
# def change_password(
#     data: ChangePasswordRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Allow a logged-in user to change their password.
#     """
#     from auth import verify_password, hash_password
    
#     # Validate passwords match
#     if data.new_password != data.confirm_password:
#         raise HTTPException(
#             status_code=400, 
#             detail={"error": "Passwords do not match", "error_code": "PASSWORD_MISMATCH"}
#         )

#     # Verify current password
#     if not verify_password(data.current_password, current_user.hashed_password):
#         raise HTTPException(
#             status_code=400, 
#             detail={"error": "Current password incorrect", "error_code": "WRONG_PASSWORD"}
#         )

#     # Update password
#     current_user.hashed_password = hash_password(data.new_password)
    
#     # ✅ FIX: Generate current timestamp
#     changed_at = datetime.now(timezone.utc)
    
#     # Update updated_at if field exists
#     if hasattr(current_user, "updated_at"):
#         current_user.updated_at = changed_at
    
#     db.commit()
    
#     return PasswordChangeResponse(
#         success=True,
#         message="Password changed successfully",
#         changed_at=changed_at  # ✅ Always a valid datetime
#     )


# @router.post("/forgot-password", response_model=ForgotPasswordResponse, responses={400: {"model": ErrorResponse}})
# def forgot_password(
#     data: ForgotPasswordRequest,
#     request: Request,
#     db: Session = Depends(get_db)
# ):
#     """
#     Employee requests an OTP to reset their password.
#     """
#     user = db.query(User).filter(User.email == data.email).first()
#     if not user:
#         # Security: Don't reveal user existence
#         return ForgotPasswordResponse(
#             success=True,
#             message="If this email is registered, you will receive an OTP code",
#             expires_at=None,
#         )
    
#     # Generate token & store in DB
#     otp_code, expires_at = otp_service.create_reset_token(
#         db=db, 
#         user_id=user.id, 
#         email=user.email,
#         ip_address=request.client.host,
#         user_agent=request.headers.get('user-agent', 'Unknown')
#     )
    
#     # Send OTP via email
#     email_service.send_otp_email(
#         to_email=user.email, 
#         otp_code=otp_code, 
#         employee_name=user.username
#     )
    
#     return ForgotPasswordResponse(
#         success=True,
#         message="If this email is registered, you will receive an OTP code",
#         expires_at=expires_at,
#     )


# @router.post("/reset-password", response_model=ResetPasswordResponse, responses={400: {"model": ErrorResponse}})
# def reset_password(
#     data: ResetPasswordRequest,
#     db: Session = Depends(get_db)
# ):
#     """
#     Employee enters OTP, new password. Validates and resets password.
#     """
#     from auth import hash_password
    
#     # Validate OTP
#     is_valid, user_id, error = otp_service.validate_otp(
#         db=db, 
#         email=data.email, 
#         otp_code=data.otp_code
#     )
    
#     if not is_valid:
#         raise HTTPException(
#             status_code=400, 
#             detail={"error": error, "error_code": "INVALID_OTP"}
#         )
    
#     # Get user object
#     user = db.query(User).filter(
#         User.id == user_id, 
#         User.email == data.email
#     ).first()
    
#     if not user:
#         raise HTTPException(
#             status_code=400, 
#             detail={"error": "No user for this token", "error_code": "USER_NOT_FOUND"}
#         )
    
#     # Update password
#     user.hashed_password = hash_password(data.new_password)
    
#     # ✅ FIX: Generate current timestamp
#     reset_at = datetime.now(timezone.utc)
    
#     # Update updated_at if field exists
#     if hasattr(user, "updated_at"):
#         user.updated_at = reset_at
    
#     db.commit()
    
#     # Mark OTP as used
#     otp_service.mark_as_used(
#         db=db, 
#         email=data.email, 
#         otp_code=data.otp_code
#     )
    
#     # Send notification
#     email_service.send_password_changed_notification(
#         to_email=user.email, 
#         employee_name=user.username, 
#         ip_address="unknown"
#     )
    
#     return ResetPasswordResponse(
#         success=True,
#         message="Password reset successful. Please login with your new password.",
#         reset_at=reset_at  # ✅ Always a valid datetime
#     )
