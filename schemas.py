from pydantic import BaseModel, field_serializer, computed_field, Field, validator, EmailStr
from typing import Optional, Literal, List
from datetime import datetime, date
from utils import to_ist
import re
from decimal import Decimal

# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    email: EmailStr
    # email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@company.com",
                "password": "SecurePass123!",
                "role": "employee",
                "phone": "+1234567890",
                "emp_code": "EMP001"
            }
        }

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str


# ROLE SCHEMAS - Added

class RoleOut(BaseModel):
    """Role information for API responses"""
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    level: int
    is_active: bool
    
    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    """Schema for creating new roles (super admin only)"""
    name: str
    display_name: str
    description: Optional[str] = None
    level: int
    is_active: bool = True
    
    @validator('name')
    def validate_role_name(cls, v):
        if not v.islower():
            raise ValueError("Role name must be lowercase")
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("Role name can only contain letters, numbers, and underscores")
        return v
    
    @validator('level')
    def validate_level(cls, v):
        """Ensure level is within reasonable range"""
        if v < 0 or v > 100:
            raise ValueError("Role level must be between 0 and 100")
        return v

class RoleUpdate(BaseModel):
    """Schema for updating existing roles"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    level: Optional[int] = None
    is_active: Optional[bool] = None
    
    @validator('level')
    def validate_level(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Role level must be between 0 and 100")
        return v

class TokenBlacklistOut(BaseModel):
    """Blacklisted token information for admin view"""
    id: int
    jti: str
    username: str
    blacklisted_at: datetime
    token_exp: datetime
    reason: str
    
    class Config:
        from_attributes = True

class LogoutResponse(BaseModel):
    """Response after successful logout"""
    message: str
    success: bool
    username: str

class TokenExtended(BaseModel):
    """Extended token response with additional info"""
    access_token: str
    token_type: str
    expires_in: int  # Seconds until expiry
    username: str
    role: str

class UserOutDetailed(BaseModel):
    id: int
    username: str
    role: str  # Backward compatible string
    role_details: Optional[RoleOut] = None
    
    class Config:
        from_attributes = True


# Employee schemas
class EmployeeCreate(BaseModel):
    name: str
    user_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None
    # NEW: Organization fields
    department_id: Optional[int] = None
    manager_id: Optional[int] = None
    employment_type: Literal["full_time", "part_time", "contract", "intern"] = "full_time"
    is_manager: bool = False
    is_leave_eligible: bool = True


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None

class EmployeeOut(BaseModel):
    id: int
    name: str
    user_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None
    username: Optional[str] = None
    # NEW: Organization fields
    department_id: Optional[int] = None
    manager_id: Optional[int] = None
    employment_type: str
    is_manager: bool
    is_leave_eligible: bool
    created_at: datetime
    updated_at: datetime
    
    @field_serializer("created_at", "updated_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    class Config:
        from_attributes = True
# Add avatar update schema
class AvatarUpdateRequest(BaseModel):
    avatar_data: str
    
# Attendance
class AttendanceCreate(BaseModel):
    employee_id: int
    login_time: datetime
    logout_time: Optional[datetime] = None
    on_leave: bool = False
    work_hours: Optional[float] = None

class AttendanceUpdate(BaseModel):
    login_time: Optional[datetime] = None
    logout_time: Optional[datetime] = None
    on_leave: Optional[bool] = None
    work_hours: Optional[float] = None

class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    login_time: datetime
    logout_time: Optional[datetime] = None
    on_leave: bool
    work_hours: Optional[float] = None

    @field_serializer("login_time")
    def serialize_login_time(self, value):
        return to_ist(value)

    @field_serializer("logout_time")
    def serialize_logout_time(self, value):
        return to_ist(value)

    @field_serializer("work_hours")
    def serialize_work_hours(self, v):
        return round(v, 2) if v is not None else None

    @computed_field
    @property
    def work_duration(self) -> Optional[str]:
        if self.work_hours is None:
            return None
        hours = int(self.work_hours)
        minutes = int((self.work_hours * 60) % 60)
        return f"{hours}h {minutes}m"

    class Config:
        from_attributes = True

# Leave request

# class LeaveRequestCreate(BaseModel):
#     employee_id: Optional[int] = None
#     start_date: datetime
#     end_date: datetime
#     leave_type: str
#     reason: Optional[str] = None

class LeaveRequestCreate(BaseModel):
    """
    Schema for creating leave request.
    System automatically calculates paid/unpaid split.
    """
    employee_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    
    duration_type: Literal["full_day", "first_half", "second_half"] = "full_day"
    half_day_date: Optional[datetime] = None
    
    leave_type: str = Field(..., description="Type of leave (Annual, Sick, etc.)")
    leave_type_id: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=500)
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be >= start_date')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-12-01T00:00:00",
                "end_date": "2025-12-04T00:00:00",
                "leave_type": "Annual Leave",
                "reason": "Family emergency"
            }
        }


class LeaveRequestUpdate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    leave_type: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class LeaveRequestOut(BaseModel):
    """Response schema with paid/unpaid breakdown and workflow status."""
    id: int
    employee_id: int
    start_date: datetime
    end_date: datetime
    
    # ✅ NEW: Half-day support
    duration_type: str
    half_day_date: Optional[datetime]
    
    # ✅ UPDATED: Decimal support
    total_days: Decimal
    paid_days: Decimal
    unpaid_days: Decimal
    
    leave_type: str
    leave_type_id: int
    reason: Optional[str]
    
    # ✅ NEW: Workflow status
    status: str
    workflow_status: str
    current_approver_id: Optional[int]
    
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    admin_notes: Optional[str]
    
    # ✅ NEW: Cancellation support
    cancellation_requested_at: Optional[datetime]
    cancellation_reason: Optional[str]
    cancelled_by_user_id: Optional[int]
    cancelled_at: Optional[datetime]
    
    created_at: datetime
    updated_at: datetime
    
    @field_serializer("start_date", "end_date", "approved_at", "created_at", "updated_at", 
                     "half_day_date", "cancellation_requested_at", "cancelled_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    @computed_field
    @property
    def payment_status(self) -> str:
        """Human-readable payment status with half-day support."""
        if self.unpaid_days == 0:
            return "Fully Paid"
        elif self.paid_days == 0:
            return "Fully Unpaid"
        else:
            return f"Partial ({float(self.paid_days)} paid, {float(self.unpaid_days)} unpaid)"
    
    class Config:
        from_attributes = True
        
        
class LeaveApprovalOut(BaseModel):
    """Response schema for leave approval information."""
    id: int
    leave_request_id: int
    level: int
    level_name: str
    approver_id: int
    status: str
    action_by_user_id: Optional[int]
    action_at: Optional[datetime]
    comments: Optional[str]
    sequence: int
    is_final: bool
    created_at: datetime
    
    @field_serializer("action_at", "created_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    class Config:
        from_attributes = True

# Old leave request output schema (before paid/unpaid split)
# class LeaveRequestOut(BaseModel):
#     """Response schema with paid/unpaid breakdown."""
#     id: int
#     employee_id: int
#     start_date: datetime
#     end_date: datetime
    
#     total_days: int
#     paid_days: int
#     unpaid_days: int
    
#     leave_type: str
#     status: str
#     reason: Optional[str]
    
#     approved_by: Optional[int]
#     approved_at: Optional[datetime]
#     admin_notes: Optional[str]
    
#     created_at: datetime
#     updated_at: datetime
    
#     @field_serializer("start_date", "end_date", "approved_at", "created_at", "updated_at")
#     def serialize_dates(self, value):
#         return to_ist(value) if value else None
    
#     @computed_field
#     @property
#     def payment_status(self) -> str:
#         """Human-readable payment status."""
#         if self.unpaid_days == 0:
#             return "Fully Paid"
#         elif self.paid_days == 0:
#             return "Fully Unpaid"
#         else:
#             return f"Partial ({self.paid_days} paid, {self.unpaid_days} unpaid)"
    
#     class Config:
#         from_attributes = True


class LeaveApprovalRequest(BaseModel):
    """Schema for admin to approve/deny leave."""
    action: Literal["approve", "deny"]
    admin_notes: Optional[str] = Field(None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "approve",
                "admin_notes": "Approved for emergency"
            }
        }

# class LeaveRequestOut(BaseModel):
#     id: int
#     employee_id: int
#     start_date: datetime
#     end_date: datetime
#     leave_type: str
#     status: str
#     reason: Optional[str]

#     @field_serializer("start_date")
#     def serialize_start_date(self, value):
#         return to_ist(value)

#     @field_serializer("end_date")
#     def serialize_end_date(self, value):
#         return to_ist(value)

#     class Config:
#         from_attributes = True

# Leave Balance (additions)
class LeaveBalanceOut(BaseModel):
    """Comprehensive leave balance with decimal support."""
    employee_id: int
    available_coins: Decimal  # Changed from int
    total_granted: Decimal
    total_consumed: Decimal
    expiring_soon: list[dict]
    recent_txns: list[dict]
    
    @field_serializer("expiring_soon")
    def serialize_expiry(self, v):
        from utils import to_ist
        out = []
        for item in v:
            out.append({
                "expiry_date": to_ist(item["expiry_date"]),
                "amount": float(item["amount"]),  # Convert Decimal to float for JSON
            })
        return out
    
    @field_serializer("recent_txns")
    def serialize_txns(self, v):
        out = []
        for t in v:
            out.append({
                "type": t["type"],
                "amount": float(t["amount"]),  # Convert Decimal to float
                "occurred_at": t["occurred_at"],
                "comment": t.get("comment"),
            })
        return out
    
    class Config:
        from_attributes = True
# WorkSession and break support
class WorkSessionStateOut(BaseModel):
    session_id: Optional[int]
    status: Optional[Literal["active", "break", "ended"]]
    clock_in_time: Optional[datetime]
    clock_out_time: Optional[datetime]
    elapsed_work_seconds: int
    elapsed_break_seconds: int

    class Config:
        from_attributes = True

class WorkSessionDayRow(BaseModel):
    date: datetime
    first_clock_in: Optional[datetime]
    last_clock_out: Optional[datetime]
    total_break_seconds: int
    total_work_seconds: int
    ot_sec: int = 0

class ClockActionResponse(BaseModel):
    session_id: int
    status: Literal["active", "break", "ended"]
    message: str


# Post schemas
class PostCreate(BaseModel):
    title: str
    content: str
    is_pinned: Optional[bool] = False

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_pinned: Optional[bool] = None
    status: Optional[str] = None

class PostOut(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    author_name: Optional[str] = None
    created_at: str
    updated_at: str
    is_pinned: bool
    status: str
    reaction_counts: Optional[dict] = {}
    user_reactions: Optional[List[str]] = []
    is_viewed: Optional[bool] = False
    
    class Config:
        from_attributes = True

# Reaction schemas
class ReactionCreate(BaseModel):
    emoji: str

class ReactionOut(BaseModel):
    id: int
    post_id: int
    user_id: int
    emoji: str
    created_at: str
    
    class Config:
        from_attributes = True

class ReactionDetail(BaseModel):
    user_id: int
    username: str
    emoji: str
    created_at: str
    
    class Config:
        from_attributes = True


class PostOutAdmin(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    author_name: Optional[str] = None
    created_at: str
    updated_at: str
    is_pinned: bool
    status: str
    reaction_counts: dict  # {"👍": 5, "❤️": 3}
    reactions: list[ReactionDetail]  # ✅ NEW: List of detailed reactions
    total_reactions: int
    view_count: int
    
    class Config:
        from_attributes = True

# Notification schemas
class UnreadCountOut(BaseModel):
    unread_count: int


# Employee Profile Update Schema
class EmployeeProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    
    class Config:
        str_strip_whitespace = True

    @validator('phone')
    def validate_phone(cls, v):
        if v is None:
            return v
        # Remove all non-digits
        digits_only = re.sub(r'\D', '', v)
        # Check if it's a valid Indian mobile number (10 digits starting with 6-9)
        if not re.match(r'^[6-9]\d{9}$', digits_only):
            raise ValueError('Phone must be a valid 10-digit mobile number')
        return digits_only

# DAILY ATTENDANCE SCHEMAS

class DailyAttendanceOut(BaseModel):
    """
    Response schema for daily aggregated attendance.
    Returns pre-calculated daily totals for fast API responses.
    """
    id: int
    employee_id: int
    attendance_date: datetime
    
    # Aggregated metrics (in seconds)
    total_work_seconds: int
    total_break_seconds: int
    session_count: int
    
    # Boundary times
    first_clock_in: Optional[datetime] = None
    last_clock_out: Optional[datetime] = None
    
    # Status: complete, partial, incomplete, absent, leave
    status: str
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    
    # Serialize datetime fields to IST
    @field_serializer("attendance_date")
    def serialize_date(self, value):
        """Convert date to IST string (date only)"""
        if value:
            return to_ist(value).split('T')[0]  # Return just the date part
        return None
    
    @field_serializer("first_clock_in", "last_clock_out")
    def serialize_times(self, value):
        """Convert datetime to IST string"""
        return to_ist(value) if value else None
    
    @field_serializer("created_at", "updated_at")
    def serialize_metadata(self, value):
        """Convert metadata timestamps to IST"""
        return to_ist(value) if value else None
    
    # Computed fields for convenience
    @computed_field
    @property
    def total_work_hours(self) -> float:
        """Total work time in hours (rounded to 2 decimals)"""
        return round(self.total_work_seconds / 3600, 2)
    
    @computed_field
    @property
    def total_break_hours(self) -> float:
        """Total break time in hours (rounded to 2 decimals)"""
        return round(self.total_break_seconds / 3600, 2)
    
    @computed_field
    @property
    def work_duration(self) -> str:
        """Human-readable work duration (e.g., '8h 30m')"""
        hours = int(self.total_work_seconds / 3600)
        minutes = int((self.total_work_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    
    @computed_field
    @property
    def break_duration(self) -> str:
        """Human-readable break duration (e.g., '1h 15m')"""
        hours = int(self.total_break_seconds / 3600)
        minutes = int((self.total_break_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    
    class Config:
        from_attributes = True


class ArchivedAttendanceOut(BaseModel):
    """
    Response schema for archived attendance records.
    Similar to DailyAttendanceOut but includes archive metadata.
    """
    id: int
    employee_id: int
    attendance_date: datetime
    
    # Aggregated metrics
    total_work_seconds: int
    total_break_seconds: int
    session_count: int
    
    # Boundary times
    first_clock_in: Optional[datetime] = None
    last_clock_out: Optional[datetime] = None
    
    # Status
    status: str
    
    # Archive metadata
    archived_at: datetime
    original_daily_id: Optional[int] = None
    
    # Serialize datetime fields to IST
    @field_serializer("attendance_date")
    def serialize_date(self, value):
        """Convert date to IST string (date only)"""
        if value:
            return to_ist(value).split('T')[0]
        return None
    
    @field_serializer("first_clock_in", "last_clock_out", "archived_at")
    def serialize_times(self, value):
        """Convert datetime to IST string"""
        return to_ist(value) if value else None
    
    # Computed fields
    @computed_field
    @property
    def total_work_hours(self) -> float:
        """Total work time in hours"""
        return round(self.total_work_seconds / 3600, 2)
    
    @computed_field
    @property
    def total_break_hours(self) -> float:
        """Total break time in hours"""
        return round(self.total_break_seconds / 3600, 2)
    
    @computed_field
    @property
    def work_duration(self) -> str:
        """Human-readable work duration"""
        hours = int(self.total_work_seconds / 3600)
        minutes = int((self.total_work_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    
    class Config:
        from_attributes = True


# ATTENDANCE SUMMARY SCHEMA
# Used for date range queries (e.g., last 14 days, last month)

class AttendanceSummaryOut(BaseModel):
    """
    Summary of attendance data for a date range.
    Combines daily_attendance and archived_attendance records.
    """
    start_date: str  # ISO date string
    end_date: str    # ISO date string
    employee_id: int
    
    # Summary metrics
    total_days: int
    days_present: int
    days_absent: int
    days_on_leave: int
    days_partial: int  # Incomplete work days
    
    # Aggregated totals (in hours)
    total_work_hours: float
    total_break_hours: float
    average_work_hours_per_day: float
    
    # Detailed daily records
    daily_records: List[DailyAttendanceOut]
    archived_records: Optional[List[ArchivedAttendanceOut]] = []
    
    # Status breakdown
    status_breakdown: dict  # {"complete": 10, "partial": 2, "absent": 1, "leave": 1}
    
    class Config:
        from_attributes = True


# ATTENDANCE QUERY PARAMETERS
# Used for filtering attendance queries

class AttendanceDateRangeQuery(BaseModel):
    """Query parameters for fetching attendance in a date range"""
    start_date: str  # ISO date string (YYYY-MM-DD)
    end_date: str    # ISO date string (YYYY-MM-DD)
    employee_id: Optional[int] = None  # If None, fetch for all employees
    include_archived: bool = True  # Whether to include archived records
    
    class Config:
        str_strip_whitespace = True


class AttendanceStatusQuery(BaseModel):
    """Query parameters for filtering by status"""
    status: Optional[Literal["complete", "partial", "incomplete", "absent", "leave"]] = None
    date: Optional[str] = None  # ISO date string (YYYY-MM-DD)
    
    class Config:
        str_strip_whitespace = True




# PASSWORD RESET & AUTHENTICATION SCHEMAS
# Purpose: Validate password reset API requests and responses

# REQUEST SCHEMAS (Client → Server)

class ChangePasswordRequest(BaseModel):
    """
    Schema for changing password while logged in.
    
    Employee has current password and wants to change it.
    Must know current password for security.
    
    Example:
        {
            "current_password": "OldPass123!",
            "new_password": "NewPass456!",
            "confirm_password": "NewPass456!"
        }
    """
    current_password: str = Field(
        ...,
        min_length=1,
        description="Current password (for verification)"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (minimum 8 characters)"
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        description="Confirm new password (must match new_password)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "MyNewPassword456!",
                "confirm_password": "MyNewPassword456!"
            }
        }


class ForgotPasswordRequest(BaseModel):
    """
    Schema for requesting password reset (OTP generation).
    
    Employee forgot password and requests OTP via email.
    Only needs email address.
    
    Example:
        {
            "email": "employee@company.com"
        }
    """
    email: EmailStr = Field(
        ...,
        description="Registered email address"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "email": "john@company.com"
            }
        }


class ResetPasswordRequest(BaseModel):
    """
    Schema for resetting password with OTP.
    
    Employee enters email, OTP code, and new password.
    System verifies OTP and updates password.
    
    Example:
        {
            "email": "employee@company.com",
            "otp_code": "482916",
            "new_password": "NewPassword789!"
        }
    """
    email: EmailStr = Field(
        ...,
        description="Email address (for verification)"
    )
    otp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern="^[0-9]{6}$",
        description="6-digit OTP code"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (minimum 8 characters)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "email": "john@company.com",
                "otp_code": "482916",
                "new_password": "MyNewPassword456!"
            }
        }

# RESPONSE SCHEMAS (Server → Client)

class PasswordChangeResponse(BaseModel):
    """
    Schema for password change response.
    
    Returned after successful password change.
    
    Example:
        {
            "success": true,
            "message": "Password changed successfully",
            "changed_at": "2025-11-17T18:05:00"
        }
    """
    success: bool = Field(
        ...,
        description="Was password change successful?"
    )
    message: str = Field(
        ...,
        description="Human-readable message"
    )
    changed_at: datetime = Field(
        ...,
        description="When was password changed (UTC)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Password changed successfully",
                "changed_at": "2025-11-17T18:05:00Z"
            }
        }


class ForgotPasswordResponse(BaseModel):
    """
    Schema for forgot password response.
    
    Returned after OTP is generated and sent.
    Does NOT reveal if email exists (security).
    
    Example:
        {
            "success": true,
            "message": "If email registered, OTP sent",
            "expires_at": "2025-11-17T18:15:00"
        }
    """
    success: bool = Field(
        ...,
        description="Operation status"
    )
    message: str = Field(
        ...,
        description="Generic message (doesn't reveal if email exists)"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="When OTP expires (UTC)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "If this email is registered, you will receive an OTP code",
                "expires_at": "2025-11-17T18:15:00Z"
            }
        }


class ResetPasswordResponse(BaseModel):
    """
    Schema for password reset response (after OTP validation).
    
    Returned after successful password reset with OTP.
    
    Example:
        {
            "success": true,
            "message": "Password reset successful",
            "reset_at": "2025-11-17T18:05:00"
        }
    """
    success: bool = Field(
        ...,
        description="Was reset successful?"
    )
    message: str = Field(
        ...,
        description="Human-readable message"
    )
    reset_at: datetime = Field(
        ...,
        description="When was password reset (UTC)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Password reset successful. Please login with your new password.",
                "reset_at": "2025-11-17T18:05:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """
    Schema for error responses.
    
    Returned when something goes wrong.
    
    Example:
        {
            "success": false,
            "error": "Invalid OTP code",
            "error_code": "INVALID_OTP"
        }
    """
    success: bool = Field(
        False,
        description="Operation failed"
    )
    error: str = Field(
        ...,
        description="Error message"
    )
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code"
    )
    details: Optional[dict] = Field(
        None,
        description="Additional error details"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "Invalid OTP code",
                "error_code": "INVALID_OTP",
                "details": {
                    "attempts_remaining": 2
                }
            }
        }


# DEPARTMENT SCHEMAS
class DepartmentCreate(BaseModel):
    """Schema for creating departments."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    parent_department_id: Optional[int] = None
    hod_employee_id: Optional[int] = None


class DepartmentUpdate(BaseModel):
    """Schema for updating departments."""
    name: Optional[str] = None
    description: Optional[str] = None
    parent_department_id: Optional[int] = None
    hod_employee_id: Optional[int] = None
    is_active: Optional[bool] = None


class DepartmentOut(BaseModel):
    """Response schema for department information."""
    id: int
    name: str
    code: str
    description: Optional[str]
    parent_department_id: Optional[int]
    hod_employee_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    @field_serializer("created_at", "updated_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    class Config:
        from_attributes = True
        
# ============================================================================
# LEAVE TYPE SCHEMAS (NEW)
# ============================================================================

class LeaveTypeCreate(BaseModel):
    """Schema for creating leave types."""
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    default_annual_quota: int = Field(default=0, ge=0)
    allow_half_day: bool = True
    requires_approval: bool = True
    uses_balance: bool = True
    min_notice_days: int = Field(default=0, ge=0)
    max_days_per_request: int = Field(default=365, ge=1)
    display_order: int = 0


class LeaveTypeUpdate(BaseModel):
    """Schema for updating leave types."""
    name: Optional[str] = None
    description: Optional[str] = None
    default_annual_quota: Optional[int] = None
    allow_half_day: Optional[bool] = None
    requires_approval: Optional[bool] = None
    uses_balance: Optional[bool] = None
    min_notice_days: Optional[int] = None
    max_days_per_request: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class LeaveTypeOut(BaseModel):
    """Response schema for leave type information."""
    id: int
    code: str
    name: str
    description: Optional[str]
    default_annual_quota: int
    allow_half_day: bool
    requires_approval: bool
    uses_balance: bool
    min_notice_days: int
    max_days_per_request: int
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
    
    @field_serializer("created_at", "updated_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    class Config:
        from_attributes = True

# ============================================================================
# NOTIFICATION SCHEMAS (NEW)
# ============================================================================

class NotificationOut(BaseModel):
    """Response schema for notification information."""
    id: int
    user_id: int
    type: str
    title: str
    message: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[int]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    
    @field_serializer("created_at", "read_at")
    def serialize_dates(self, value):
        return to_ist(value) if value else None
    
    class Config:
        from_attributes = True
        
# MANUAL ATTENDANCE ADJUSTMENT SCHEMAS
# Purpose: Schemas for manual attendance correction feature

class AttendanceAdjustmentRequest(BaseModel):
    """
    Input schema for manual attendance adjustment requests.
    
    Used by Admin to correct missed or incorrect clock in/out times.
    
    Attributes:
        first_clock_in: New first clock-in time (optional if only adjusting clock-out)
        last_clock_out: New last clock-out time (optional if only adjusting clock-in)
        reason: Mandatory explanation for the adjustment (min 10 characters)
    
    Example:
        {
            "first_clock_in": "2024-11-26T09:00:00",
            "last_clock_out": "2024-11-26T18:00:00",
            "reason": "Employee forgot to clock in due to system maintenance"
        }
    """
    first_clock_in: Optional[datetime] = Field(
        None, 
        description="New first clock-in time for the day"
    )
    last_clock_out: Optional[datetime] = Field(
        None,
        description="New last clock-out time for the day"
    )
    reason: str = Field(
        ..., 
        min_length=10, 
        max_length=500,
        description="Mandatory reason for adjustment (minimum 10 characters)"
    )
    
    @validator('reason')
    def validate_reason(cls, v):
        """Ensure reason is not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError('Adjustment reason cannot be empty or whitespace')
        return v.strip()
    
    @validator('last_clock_out')
    def validate_times(cls, last_clock_out, values):
        """Ensure last_clock_out is after first_clock_in if both provided"""
        first_clock_in = values.get('first_clock_in')
        if first_clock_in and last_clock_out:
            if last_clock_out <= first_clock_in:
                raise ValueError('Last clock out time must be after first clock in time')
        return last_clock_out
    
    class Config:
        json_schema_extra = {
            "example": {
                "first_clock_in": "2024-11-26T09:00:00",
                "last_clock_out": "2024-11-26T18:00:00",
                "reason": "Employee forgot to clock in due to system maintenance issue"
            }
        }


class AttendanceAdjustmentOut(BaseModel):
    """
    Output schema for adjusted attendance record.
    
    Returns complete attendance details after successful adjustment,
    including adjustment metadata for audit trail.
    
    Attributes:
        id: Attendance record ID
        employee_id: Employee ID
        employee_name: Employee full name
        emp_code: Employee code
        attendance_date: Date of attendance
        first_clock_in: First clock-in time (adjusted)
        last_clock_out: Last clock-out time (adjusted)
        total_work_hours: Recalculated total work hours
        total_break_hours: Total break hours
        status: Attendance status (complete/partial/incomplete/absent)
        is_manually_adjusted: Flag indicating manual adjustment
        adjustment_reason: Reason for adjustment
        adjusted_by_username: Username who made the adjustment
        adjusted_at: Timestamp of adjustment
    """
    id: int
    employee_id: int
    employee_name: str
    emp_code: str
    attendance_date: datetime
    first_clock_in: Optional[datetime]
    last_clock_out: Optional[datetime]
    total_work_hours: float
    total_break_hours: float
    status: str
    
    # Adjustment tracking fields
    is_manually_adjusted: bool
    adjustment_reason: Optional[str]
    adjusted_by_username: Optional[str]
    adjusted_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 123,
                "employee_id": 45,
                "employee_name": "John Doe",
                "emp_code": "EMP001",
                "attendance_date": "2024-11-26T00:00:00",
                "first_clock_in": "2024-11-26T09:00:00",
                "last_clock_out": "2024-11-26T18:00:00",
                "total_work_hours": 8.5,
                "total_break_hours": 0.5,
                "status": "complete",
                "is_manually_adjusted": True,
                "adjustment_reason": "Employee forgot to clock in due to system issue",
                "adjusted_by_username": "admin",
                "adjusted_at": "2024-11-26T14:30:00"
            }
        }


class AttendanceAdjustmentHistoryOut(BaseModel):
    """
    Output schema for attendance adjustment history records.
    
    Used by admin to view audit trail of all manual adjustments.
    Provides comprehensive information for compliance and reporting.
    
    Attributes:
        attendance_date: Date of the adjusted attendance
        employee_name: Employee full name
        emp_code: Employee code
        department: Department name
        adjusted_by: Username who made the adjustment
        adjustment_reason: Reason for adjustment
        adjusted_at: Timestamp when adjustment was made
    """
    attendance_date: date
    employee_name: str
    emp_code: str
    department: str
    adjusted_by: str
    adjustment_reason: str
    adjusted_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "attendance_date": "2024-11-26",
                "employee_name": "John Doe",
                "emp_code": "EMP001",
                "department": "Engineering",
                "adjusted_by": "admin",
                "adjustment_reason": "System error during clock-in process",
                "adjusted_at": "2024-11-26T14:30:00"
            }
        }


# WORK NOTES SCHEMAS
# Purpose: Track daily work plans and completed tasks

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, validator, computed_field

class ClockInRequest(BaseModel):
    """
    Schema for clock-in request with work plan.
    
    Required fields:
    - department_id: Department where work will be performed
    - work_plan: Description of planned tasks for the day
    
    Validations:
    - department_id must exist in departments table
    - work_plan minimum 10 characters
    - work_plan maximum 2000 characters
    """
    department_id: int = Field(
        ..., 
        gt=0,
        description="Department ID (must be valid and active)"
    )
    work_plan: str = Field(
        ..., 
        min_length=10, 
        max_length=2000,
        description="Today's work plan/tasks (minimum 10 characters)"
    )
    
    @validator('work_plan')
    def validate_work_plan(cls, v):
        """Ensure work plan is not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError('Work plan cannot be empty or only whitespace')
        if len(v.strip()) < 10:
            raise ValueError('Work plan must be at least 10 characters long')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "department_id": 3,
                "work_plan": "Complete leave management feature implementation, review PR #45, attend team standup meeting at 10 AM"
            }
        }


class ClockOutRequest(BaseModel):
    """
    Schema for clock-out request with completed tasks.
    
    Required fields:
    - tasks_completed: Description of tasks completed during the session
    
    Validations:
    - tasks_completed minimum 10 characters
    - tasks_completed maximum 2000 characters
    """
    tasks_completed: str = Field(
        ..., 
        min_length=10, 
        max_length=2000,
        description="Tasks completed today (minimum 10 characters)"
    )
    
    @validator('tasks_completed')
    def validate_tasks(cls, v):
        """Ensure tasks completed is not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError('Tasks completed cannot be empty or only whitespace')
        if len(v.strip()) < 10:
            raise ValueError('Tasks completed must be at least 10 characters long')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "tasks_completed": "Completed leave API endpoints, deployed to staging environment, fixed 3 critical bugs, attended 2 client meetings"
            }
        }


class WorkSessionOut(BaseModel):
    """
    Enhanced work session output with work notes.
    
    Includes all session details plus work planning information:
    - department_id and department_name
    - work_plan (entered at clock-in)
    - tasks_completed (entered at clock-out)
    - notes_updated_at (last update timestamp)
    """
    id: int
    employee_id: int
    clock_in_time: datetime
    clock_out_time: Optional[datetime]
    status: str
    total_work_seconds: int
    
    # ✅ NEW: Work Notes Fields
    department_id: Optional[int]
    department_name: Optional[str]  # Populated from department relationship
    work_plan: Optional[str]
    tasks_completed: Optional[str]
    notes_updated_at: Optional[datetime]
    
    @field_serializer("clock_in_time", "clock_out_time", "notes_updated_at")
    def serialize_dates(self, value):
        """Convert datetime to IST string"""
        from utils import to_ist
        return to_ist(value) if value else None
    
    @computed_field
    @property
    def total_work_hours(self) -> float:
        """Total work time in hours (rounded to 2 decimals)"""
        return round(self.total_work_seconds / 3600, 2)
    
    @computed_field
    @property
    def work_duration(self) -> str:
        """Human-readable work duration (e.g., '8h 30m')"""
        hours = int(self.total_work_seconds / 3600)
        minutes = int((self.total_work_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 123,
                "employee_id": 45,
                "clock_in_time": "2025-11-26T09:00:00+05:30",
                "clock_out_time": "2025-11-26T18:00:00+05:30",
                "status": "ended",
                "total_work_seconds": 32400,
                "department_id": 3,
                "department_name": "Engineering",
                "work_plan": "Complete API development and testing",
                "tasks_completed": "Completed all API endpoints, fixed bugs, deployed to staging",
                "notes_updated_at": "2025-11-26T18:00:00+05:30",
                "total_work_hours": 9.0,
                "work_duration": "9h 0m"
            }
        }


class WorkNotesHistoryOut(BaseModel):
    """
    Schema for work notes history query results.
    Simplified view focusing on work planning information.
    """
    date: date
    department_name: Optional[str]
    work_plan: Optional[str]
    tasks_completed: Optional[str]
    total_work_hours: float
    status: str
    
    class Config:
        from_attributes = True
