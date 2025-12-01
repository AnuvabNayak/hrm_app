from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    UniqueConstraint,
    Unicode,
    Numeric,
    Date,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime, timezone

# TIMEZONE ARCHITECTURE NOTES:
# =================================
# - ALL DateTime fields in database store UTC time as naive datetime
# - Use services.timezone_utils for IST conversion in API responses
# - Database storage remains UTC for consistency, performance, and global compatibility

class Base(DeclarativeBase):
    pass

# ============================================================================
# ROLE MODEL (UNCHANGED)
# ============================================================================

class Role(Base):
    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    level = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    users = relationship("User", back_populates="role_rel")
    
    def __repr__(self):
        return f"<Role {self.name} (level={self.level})>"


# ============================================================================
# TOKEN BLACKLIST MODEL (UNCHANGED)
# ============================================================================

class TokenBlacklist(Base):
    __tablename__ = 'token_blacklist'
    
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    username = Column(String(15), nullable=False)
    blacklisted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    token_exp = Column(DateTime, nullable=False)
    reason = Column(String(50), default="user_logout")
    
    user = relationship("User", back_populates="blacklisted_tokens")
    
    __table_args__ = (
        Index('idx_blacklist_jti', 'jti'),
        Index('idx_blacklist_user_id', 'user_id'),
        Index('idx_blacklist_exp', 'token_exp'),
    )


# ============================================================================
# USER MODEL (UPDATED with Notifications)
# ============================================================================

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(15), unique=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String)
    
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=True)
    role = Column(String, default="employee") # Legacy
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)) 
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    role_rel = relationship("Role", back_populates="users")
    posts = relationship("Post", back_populates="author")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    employee = relationship("Employee", back_populates="user", uselist=False)
    blacklisted_tokens = relationship("TokenBlacklist", back_populates="user")
    
    # ✅ NEW: Notifications Relationship
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    @property
    def role_name(self) -> str:
        if self.role_rel:
            return self.role_rel.name
        return self.role if self.role else "employee"
    
    @property
    def role_level(self) -> int:
        if self.role_rel:
            return self.role_rel.level
        role_map = {"employee": 0, "admin": 50, "super_admin": 100}
        return role_map.get(self.role, 0)
    
    def __repr__(self):
        return f"<User {self.username} ({self.role_name})>"


# ============================================================================
# DEPARTMENT MODEL (NEW)
# ============================================================================

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    
    # Hierarchy
    parent_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    
    # Leadership
    hod_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relationships
    parent = relationship("Department", remote_side=[id], backref="sub_departments")
    # Use string reference for Employee to avoid circular import issues
    head_of_department = relationship("Employee", foreign_keys=[hod_employee_id], post_update=True)
    employees = relationship("Employee", foreign_keys="Employee.department_id", back_populates="department")
    
    def __repr__(self):
        return f"<Department {self.code}>"


# ============================================================================
# EMPLOYEE MODEL (UPDATED with Hierarchy & Dept)
# ============================================================================

class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    emp_code = Column(String, nullable=True)
    
    # ✅ NEW: Organization & Permissions
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    employment_type = Column(String(20), default="full_time") 
    is_manager = Column(Boolean, default=False)
    is_leave_eligible = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="employee")
    department = relationship("Department", foreign_keys=[department_id], back_populates="employees")
    
    # Self-referential relationship for Manager Hierarchy
    manager = relationship("Employee", remote_side=[id], backref="direct_reports", foreign_keys=[manager_id])
    
    # Leave Relationships
    leave_requests = relationship("LeaveRequest", foreign_keys="LeaveRequest.employee_id", back_populates="employee")
    
    location_permission = relationship("LocationPermission", back_populates="employee", uselist=False)
    
    __table_args__ = (UniqueConstraint('user_id', name='_user_id_uc'),)
    
    def __repr__(self):
        return f"<Employee {self.name} (emp_code={self.emp_code})>"


# ============================================================================
# LEAVE TYPE MODEL (NEW)
# ============================================================================

class LeaveType(Base):
    __tablename__ = "leave_types"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Balance & Quota
    default_annual_quota = Column(Integer, default=0)
    
    # Request Rules
    allow_half_day = Column(Boolean, default=True)
    requires_approval = Column(Boolean, default=True)
    uses_balance = Column(Boolean, default=True)
    min_notice_days = Column(Integer, default=0)
    max_days_per_request = Column(Integer, default=365)
    
    # Status
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    leave_requests = relationship("LeaveRequest", back_populates="leave_type_obj")


# ============================================================================
# ATTENDANCE MODELS (UNCHANGED)
# ============================================================================

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'))
    login_time = Column(DateTime)
    logout_time = Column(DateTime)
    on_leave = Column(Boolean, default=False)
    work_hours = Column(Float)

class WorkSession(Base):
    __tablename__ = "work_sessions"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    clock_in_time = Column(DateTime, nullable=False)
    clock_out_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="active") 
    total_work_seconds = Column(Integer, nullable=False, default=0)
    daily_attendance_id = Column(Integer, ForeignKey('daily_attendance.id'), nullable=True)
    # WORK NOTES FIELDS
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    work_plan = Column(Text, nullable=True)
    tasks_completed = Column(Text, nullable=True)
    notes_updated_at = Column(DateTime, nullable=True)
    
    daily_attendance = relationship("DailyAttendance", back_populates="work_sessions")
    employee = relationship("Employee")
    department = relationship("Department")

class DailyAttendance(Base):
    __tablename__ = 'daily_attendance'
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    attendance_date = Column(DateTime, nullable=False)
    total_work_seconds = Column(Integer, nullable=False, default=0)
    total_break_seconds = Column(Integer, nullable=False, default=0)
    session_count = Column(Integer, nullable=False, default=0)
    first_clock_in = Column(DateTime, nullable=True)
    last_clock_out = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default='incomplete')
    # MANUAL ADJUSTMENT TRACKING
    is_manually_adjusted = Column(Boolean, default=False, nullable=False)
    adjusted_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    adjustment_reason = Column(Text, nullable=True)
    adjusted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relationships
    employee = relationship("Employee")
    work_sessions = relationship("WorkSession", back_populates="daily_attendance")
    adjusted_by = relationship("User", foreign_keys=[adjusted_by_user_id])  # NEW

    # employee = relationship("Employee")
    # work_sessions = relationship("WorkSession", back_populates="daily_attendance")
    __table_args__ = (
        Index('idx_daily_attendance_date', 'attendance_date'),
        Index('idx_daily_attendance_employee_date', 'employee_id', 'attendance_date'),
        Index('idx_daily_attendance_status', 'status', 'attendance_date'),
        UniqueConstraint('employee_id', 'attendance_date', name='unique_employee_date'),
    )
    @property
    def total_work_hours(self) -> float:
        return round(self.total_work_seconds / 3600, 2)
    @property
    def total_break_hours(self) -> float:
        return round(self.total_break_seconds / 3600, 2)

class ArchivedAttendance(Base):
    __tablename__ = 'archived_attendance'
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    attendance_date = Column(DateTime, nullable=False)
    total_work_seconds = Column(Integer, nullable=False)
    total_break_seconds = Column(Integer, nullable=False)
    session_count = Column(Integer, nullable=False)
    first_clock_in = Column(DateTime, nullable=True)
    last_clock_out = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)
    # MANUAL ADJUSTMENT TRACKING
    is_manually_adjusted = Column(Boolean, default=False, nullable=False)
    adjusted_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    adjustment_reason = Column(Text, nullable=True)
    adjusted_at = Column(DateTime, nullable=True)
    
    archived_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    original_daily_id = Column(Integer, nullable=True)
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    adjusted_by = relationship("User", foreign_keys=[adjusted_by_user_id])  # NEW
    __table_args__ = (
        Index('idx_archived_attendance_employee_date', 'employee_id', 'attendance_date'),
        Index('idx_archived_attendance_date', 'attendance_date'),
    )

class BreakInterval(Base):
    __tablename__ = "break_intervals"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("work_sessions.id"), index=True, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    id = Column(Integer, primary_key=True, index=True)
    date_utc = Column(DateTime, unique=True, index=True, nullable=False)
    text = Column(String, nullable=False)
    author = Column(String, nullable=True)


# ============================================================================
# LEAVE MODELS (UPDATED & EXPANDED)
# ============================================================================

class LeaveRequest(Base):
    """
    Enhanced leave request with hybrid policy, half-day support, and workflow.
    """
    __tablename__ = "leave_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Date range
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # ✅ NEW: Half-Day & Decimal Support
    duration_type = Column(String(20), default="full_day", nullable=False) # full_day, first_half, second_half
    half_day_date = Column(Date, nullable=True)
    
    # ✅ UPDATED: Using Numeric(Decimal) instead of Integer for days
    total_days = Column(Numeric(5, 1), nullable=False)
    paid_days = Column(Numeric(5, 1), nullable=False, default=0.0)
    unpaid_days = Column(Numeric(5, 1), nullable=False, default=0.0)
    
    # ✅ NEW: Leave Type Association
    leave_type = Column(String, nullable=False) # Keeping string for legacy logs/display
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False)
    
    reason = Column(String, nullable=True)
    
    # ✅ UPDATED: Workflow Status
    status = Column(String(20), nullable=False, default="pending")
    workflow_status = Column(String(30), default="pending_manager")
    current_approver_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # Final Approval
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)
    
    # ✅ NEW: Cancellation
    cancellation_requested_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(500), nullable=True)
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="leave_requests")
    leave_type_obj = relationship("LeaveType", back_populates="leave_requests")
    approver = relationship("User", foreign_keys=[approved_by])
    current_approver = relationship("Employee", foreign_keys=[current_approver_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_user_id])
    approvals = relationship("LeaveApproval", back_populates="leave_request", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("total_days = paid_days + unpaid_days", name="CHK_leave_days_valid"),
        CheckConstraint("total_days > 0 AND paid_days >= 0 AND unpaid_days >= 0", name="CHK_days_positive"),
        Index("idx_leave_requests_workflow", "workflow_status", "current_approver_id"),
    )
    
    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, emp_id={self.employee_id}, total={self.total_days}, status={self.status})>"


class LeaveApproval(Base):
    """Multi-level approval workflow for leave requests."""
    __tablename__ = "leave_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False)
    
    # Approval Level
    level = Column(Integer, nullable=False) # 1=manager, 2=HR
    level_name = Column(String(50), nullable=False) 
    approver_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Status
    status = Column(String(20), default="pending", nullable=False)
    
    # Action Details
    action_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_at = Column(DateTime, nullable=True)
    comments = Column(String(1000), nullable=True)
    
    # Metadata
    sequence = Column(Integer, nullable=False)
    is_final = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relationships
    leave_request = relationship("LeaveRequest", back_populates="approvals")
    approver = relationship("Employee", foreign_keys=[approver_id])
    action_by = relationship("User", foreign_keys=[action_by_user_id])


class EmployeeCoin(Base):
    """Legacy Table - kept for backward compatibility if needed"""
    __tablename__ = "employee_coins"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    accrual_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    status = Column(String, default="active") 
    spent_on = Column(DateTime, nullable=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)


class LeaveCoin(Base):
    """Leave balance tracking - UPDATED for decimal support"""
    __tablename__ = "leave_coins"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    grant_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    
    # ✅ UPDATED: Decimal support
    quantity = Column(Numeric(5, 1), nullable=False, default=1.0) # Was 'quantity' in old, 'granted' in new SQL. Keeping 'quantity' to match old Python but updated type
    remaining = Column(Numeric(5, 1), nullable=False, default=1.0)
    
    source = Column(String, nullable=False, default="monthly_grant")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    employee = relationship("Employee")
    
    __table_args__ = (
        Index("ix_leave_coins_employee_expiry", "employee_id", "expiry_date"),
    )


class LeaveCoinTxn(Base):
    """Leave transaction history - UPDATED for decimal support"""
    __tablename__ = "leave_coin_txn"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    coin_id = Column(Integer, ForeignKey("leave_coins.id"), nullable=True)
    type = Column(String, nullable=False) 
    
    # ✅ UPDATED: Decimal support
    amount = Column(Numeric(5, 1), nullable=False)
    
    ref_leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    comment = Column(String, nullable=True)
    
    employee = relationship("Employee")
    coin = relationship("LeaveCoin")


# ============================================================================
# NOTIFICATION MODEL (NEW)
# ============================================================================

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Notification Details
    type = Column(String(50), nullable=False)
    title = Column(Unicode(200), nullable=False)
    message = Column(Unicode(1000), nullable=False)
    
    # Related Entity
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(Integer, nullable=True)
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user = relationship("User", back_populates="notifications")
    
    __table_args__ = (
        Index("idx_notifications_user", "user_id", "is_read"),
    )


# ============================================================================
# POST MODELS (UNCHANGED)
# ============================================================================

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Unicode(255), nullable=False)
    content = Column(Unicode, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_pinned = Column(Boolean, default=False)
    status = Column(String(20), default="published")
    author = relationship("User", back_populates="posts")
    reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")
    views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")

class PostReaction(Base):
    __tablename__ = "post_reactions"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(Unicode(20), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    post = relationship("Post", back_populates="reactions")
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', 'emoji', name='uc_post_user_emoji'),
    )

class PostView(Base):
    __tablename__ = "post_views"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    viewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    post = relationship("Post", back_populates="views")
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='uc_post_user_view'),
    )

# ============================================================================
# PASSWORD RESET TOKEN MODEL (UNCHANGED)
# ============================================================================

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email = Column(String(255), nullable=False, index=True)
    otp_code = Column(String(6), nullable=True, index=True)
    token = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    user = relationship("User", back_populates="password_reset_tokens")
    
    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id} email={self.email} used={self.is_used}>"
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def time_remaining(self) -> int:
        if self.is_expired():
            return 0
        delta = self.expires_at - datetime.utcnow()
        return int(delta.total_seconds())


# ============================================================================
# LOCATION TRACKING MODELS (Add to end of models.py)
# ============================================================================

from enum import Enum as PyEnum

# IMPORTANT: Add this import at the TOP of models.py if not already present:
# from sqlalchemy import Index

class LocationPermissionStatus(str, PyEnum):
    """Track permission status - GDPR compliance"""
    NEVER_ASKED = "never_asked"      # Initial state
    GRANTED = "granted"              # User allowed access
    DENIED = "denied"                # User denied access
    REVOKED = "revoked"              # User revoked after granting


class LocationPermission(Base):
    """
    Track if employee allowed location tracking.
    GDPR: Explicit consent required before tracking.
    
    One record per employee (unique constraint)
    """
    __tablename__ = "location_permissions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, unique=True)
    
    # Permission status
    status = Column(
        String(20),
        default=LocationPermissionStatus.NEVER_ASKED,
        nullable=False,
        index=True
    )
    
    # When did they give/revoke permission?
    granted_at = Column(DateTime, nullable=True)         # When they allowed
    revoked_at = Column(DateTime, nullable=True)         # When they revoked
    
    # Tracking preferences
    track_always = Column(Boolean, default=False)        # Track 24/7 or only during work?
    track_work_hours_only = Column(Boolean, default=True) # Only 9AM-6PM tracking
    
    # Audit trail
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    # Relationship
    employee = relationship("Employee", back_populates="location_permission")
    location_records = relationship("EmployeeLocation", back_populates="permission", cascade="all, delete-orphan")


class EmployeeLocation(Base):
    """
    Real-time location data for employees.
    GDPR: Only store if permission is GRANTED.
    Only admins/managers can view this.
    
    Auto-delete after 90 days (see cleanup jobs)
    """
    __tablename__ = "employee_locations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("location_permissions.id"), nullable=False)
    
    # GPS coordinates
    latitude = Column(Float, nullable=False)   # -90 to +90 degrees
    longitude = Column(Float, nullable=False)  # -180 to +180 degrees
    
    # Location accuracy (in meters)
    accuracy = Column(Float, nullable=True)    # GPS accuracy: 5m, 10m, etc.
    
    # Location metadata
    address = Column(String(500), nullable=True)  # Reverse geocoding (optional)
    location_source = Column(String(50), default="gps")  # "gps", "wifi", "cellular"
    
    # Timestamps
    recorded_at = Column(DateTime, nullable=False, index=True)  # When location was captured
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    # Relationships
    employee = relationship("Employee")
    permission = relationship("LocationPermission", back_populates="location_records")
    
    # Performance: Composite index for querying by employee and date
    __table_args__ = (
        Index('idx_employee_locations_date', 'employee_id', 'recorded_at'),
    )


class LocationAccessLog(Base):
    """
    Audit trail: Who viewed whose location data?
    GDPR: Track all data access for compliance audits.
    """
    __tablename__ = "location_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Who accessed?
    accessing_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    accessing_user_role = Column(String(50), nullable=False)  # "admin", "manager"
    
    # Whose data was accessed?
    viewed_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # When?
    accessed_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True
    )
    
    # What was viewed? (in case they request data deletion)
    action = Column(String(100))  # "viewed_location", "exported_history", etc.
    
    # IP address (for security audit)
    ip_address = Column(String(50), nullable=True)


# IMPORTANT: Update Employee model relationship (if not already present)
# Add this to your Employee class:
# location_permission = relationship("LocationPermission", back_populates="employee", uselist=False)






# LAST UPDATED: JUNE 2024
# from sqlalchemy import (
#     BigInteger,
#     Boolean,
#     Column,
#     DateTime,
#     Float,
#     ForeignKey,
#     Integer,
#     Index,
#     String,
#     Text,
#     UniqueConstraint,
#     Unicode,
#     func,
# )
# from sqlalchemy.orm import relationship, DeclarativeBase
# from sqlalchemy.ext.declarative import declarative_base
# from datetime import datetime, timezone

# # TIMEZONE ARCHITECTURE NOTES:
# # =================================
# # - ALL DateTime fields in database store UTC time as naive datetime
# # - Use services.timezone_utils for IST conversion in API responses
# # - Database storage remains UTC for consistency, performance, and global compatibility

# class Base(DeclarativeBase):
#     pass

# # ============================================================================
# # ROLE MODEL
# # ============================================================================

# class Role(Base):
#     """
#     Role lookup table for user authorization.
#     Provides hierarchical role management with levels:
#     - 0: employee (basic access)
#     - 50: admin (management access)
#     - 100: super_admin (full system access)
#     """
#     __tablename__ = 'roles'
    
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(50), unique=True, nullable=False, index=True)
#     display_name = Column(String(100), nullable=False)
#     description = Column(String(255), nullable=True)
#     level = Column(Integer, nullable=False, default=0)
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
#     # Relationship back to users
#     users = relationship("User", back_populates="role_rel")
    
#     def __repr__(self):
#         return f"<Role {self.name} (level={self.level})>"


# # ============================================================================
# # TOKEN BLACKLIST MODEL
# # ============================================================================

# class TokenBlacklist(Base):
#     """
#     Track invalidated JWT tokens for logout functionality.
#     When a user logs out, their token's JTI is added here.
#     During authentication, tokens are checked against this table.
#     Expired tokens are periodically cleaned up.
#     """
#     __tablename__ = 'token_blacklist'
    
#     id = Column(Integer, primary_key=True, index=True)
#     jti = Column(String(50), unique=True, nullable=False, index=True)  # JWT ID from token
#     user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
#     username = Column(String(15), nullable=False)
#     blacklisted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     token_exp = Column(DateTime, nullable=False)  # When token would have expired naturally
#     reason = Column(String(50), default="user_logout")  # "user_logout", "admin_revoke", "security"
    
#     # ✅ FIX: Add the missing relationship!
#     user = relationship("User", back_populates="blacklisted_tokens")
    
#     # Indexes for fast lookups
#     __table_args__ = (
#         Index('idx_blacklist_jti', 'jti'),
#         Index('idx_blacklist_user_id', 'user_id'),
#         Index('idx_blacklist_exp', 'token_exp'),
#     )
    
#     def __repr__(self):
#         return f"<TokenBlacklist jti={self.jti[:8]}... user={self.username}>"


# # ============================================================================
# # USER MODEL
# # ============================================================================

# class User(Base):
#     __tablename__ = 'users'
    
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String(15), unique=True, index=True)
#     email = Column(String(255), unique=True, index=True, nullable=False)
#     hashed_password = Column(String)
    
#     # Foreign key to roles table
#     role_id = Column(Integer, ForeignKey('roles.id'), nullable=True)
#     role = Column(String, default="employee")  # Legacy column for backward compatibility
    
#     # Timestamps
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
#     # ✅ FIX: Remove duplicate role_obj, keep only role_rel
#     # Relationships
#     role_rel = relationship("Role", back_populates="users")
#     posts = relationship("Post", back_populates="author")
#     password_reset_tokens = relationship(
#         "PasswordResetToken",
#         back_populates="user",
#         cascade="all, delete-orphan"
#     )
#     employee = relationship("Employee", back_populates="user", uselist=False)
#     blacklisted_tokens = relationship("TokenBlacklist", back_populates="user")
    
#     @property
#     def role_name(self) -> str:
#         """Get role name from relationship or fallback to legacy column"""
#         if self.role_rel:
#             return self.role_rel.name
#         return self.role if self.role else "employee"
    
#     @property
#     def role_level(self) -> int:
#         """Get role level for permission checks"""
#         if self.role_rel:
#             return self.role_rel.level
#         # Fallback mapping for old role column
#         role_map = {"employee": 0, "admin": 50, "super_admin": 100}
#         return role_map.get(self.role, 0)
    
#     def __repr__(self):
#         return f"<User {self.username} ({self.role_name})>"


# # ============================================================================
# # EMPLOYEE MODEL
# # ============================================================================

# class Employee(Base):
#     __tablename__ = 'employees'
    
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String)
#     user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
#     email = Column(String, nullable=True)
#     phone = Column(String, nullable=True)
#     avatar_url = Column(String, nullable=True)
#     emp_code = Column(String, nullable=True)
    
#     user = relationship("User", back_populates="employee")
    
#     __table_args__ = (UniqueConstraint('user_id', name='_user_id_uc'),)
    
#     def __repr__(self):
#         return f"<Employee {self.name} (emp_code={self.emp_code})>"


# # ============================================================================
# # ATTENDANCE MODELS
# # ============================================================================

# class Attendance(Base):
#     __tablename__ = 'attendance'
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey('employees.id'))
#     login_time = Column(DateTime)
#     logout_time = Column(DateTime)
#     on_leave = Column(Boolean, default=False)
#     work_hours = Column(Float)


# class WorkSession(Base):
#     __tablename__ = "work_sessions"
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     clock_in_time = Column(DateTime, nullable=False)
#     clock_out_time = Column(DateTime, nullable=True)
#     status = Column(String, nullable=False, default="active")  # "active" | "break" | "ended"
#     total_work_seconds = Column(Integer, nullable=False, default=0)
#     daily_attendance_id = Column(Integer, ForeignKey('daily_attendance.id'), nullable=True)
    
#     daily_attendance = relationship("DailyAttendance", back_populates="work_sessions")
#     employee = relationship("Employee")


# class DailyAttendance(Base):
#     """
#     Daily aggregated attendance for each employee.
#     Stores last 30 days of attendance data for fast access.
#     """
#     __tablename__ = 'daily_attendance'
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
#     attendance_date = Column(DateTime, nullable=False)
#     total_work_seconds = Column(Integer, nullable=False, default=0)
#     total_break_seconds = Column(Integer, nullable=False, default=0)
#     session_count = Column(Integer, nullable=False, default=0)
#     first_clock_in = Column(DateTime, nullable=True)
#     last_clock_out = Column(DateTime, nullable=True)
#     status = Column(String(20), nullable=False, default='incomplete')
#     created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
#     employee = relationship("Employee")
#     work_sessions = relationship("WorkSession", back_populates="daily_attendance")
    
#     __table_args__ = (
#         Index('idx_daily_attendance_date', 'attendance_date'),
#         Index('idx_daily_attendance_employee_date', 'employee_id', 'attendance_date'),
#         Index('idx_daily_attendance_status', 'status', 'attendance_date'),
#         UniqueConstraint('employee_id', 'attendance_date', name='unique_employee_date'),
#     )
    
#     @property
#     def total_work_hours(self) -> float:
#         return round(self.total_work_seconds / 3600, 2)
    
#     @property
#     def total_break_hours(self) -> float:
#         return round(self.total_break_seconds / 3600, 2)


# class ArchivedAttendance(Base):
#     """
#     Archived attendance data older than 30 days.
#     Stored for compliance and reporting (1 year retention).
#     """
#     __tablename__ = 'archived_attendance'
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
#     attendance_date = Column(DateTime, nullable=False)
#     total_work_seconds = Column(Integer, nullable=False)
#     total_break_seconds = Column(Integer, nullable=False)
#     session_count = Column(Integer, nullable=False)
#     first_clock_in = Column(DateTime, nullable=True)
#     last_clock_out = Column(DateTime, nullable=True)
#     status = Column(String(20), nullable=False)
#     archived_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     original_daily_id = Column(Integer, nullable=True)
    
#     employee = relationship("Employee")
    
#     __table_args__ = (
#         Index('idx_archived_attendance_employee_date', 'employee_id', 'attendance_date'),
#         Index('idx_archived_attendance_date', 'attendance_date'),
#     )
    
#     @property
#     def total_work_hours(self) -> float:
#         return round(self.total_work_seconds / 3600, 2)
    
#     @property
#     def total_break_hours(self) -> float:
#         return round(self.total_break_seconds / 3600, 2)


# class BreakInterval(Base):
#     __tablename__ = "break_intervals"
    
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(Integer, ForeignKey("work_sessions.id"), index=True, nullable=False)
#     start_time = Column(DateTime, nullable=False)
#     end_time = Column(DateTime, nullable=True)


# # ============================================================================
# # QUOTE MODEL
# # ============================================================================

# class DailyQuote(Base):
#     __tablename__ = "daily_quotes"
    
#     id = Column(Integer, primary_key=True, index=True)
#     date_utc = Column(DateTime, unique=True, index=True, nullable=False)
#     text = Column(String, nullable=False)
#     author = Column(String, nullable=True)


# # ============================================================================
# # LEAVE MODELS
# # ============================================================================

# class LeaveRequest(Base):
#     """
#     Leave Request Model with Hybrid Leave Policy.
    
#     Supports automatic paid/unpaid split based on available balance:
#     - total_days: Total days requested
#     - paid_days: Days covered by leave coins
#     - unpaid_days: Days without pay (salary deduction)
    
#     Example:
#         Employee has 2 coins, requests 4 days
#         → paid_days=2, unpaid_days=2
#     """
#     __tablename__ = "leave_requests"
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
#     # Date range
#     start_date = Column(DateTime, nullable=False)
#     end_date = Column(DateTime, nullable=False)
    
#     # Day breakdown for hybrid policy
#     total_days = Column(Integer, nullable=False)
#     paid_days = Column(Integer, nullable=False, default=0)
#     unpaid_days = Column(Integer, nullable=False, default=0)
    
#     # Leave details
#     leave_type = Column(String, nullable=False)
#     status = Column(String(20), nullable=False, default="pending")
#     reason = Column(String, nullable=True)
    
#     # Approval tracking
#     approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
#     approved_at = Column(DateTime, nullable=True)
#     admin_notes = Column(Text, nullable=True)
    
#     # Timestamps
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
#     # Relationships
#     employee = relationship("Employee")
#     approver = relationship("User", foreign_keys=[approved_by])
    
#     def __repr__(self):
#         return f"<LeaveRequest(id={self.id}, emp_id={self.employee_id}, total={self.total_days}, paid={self.paid_days}, unpaid={self.unpaid_days}, status={self.status})>"


# class EmployeeCoin(Base):
#     __tablename__ = "employee_coins"
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
#     accrual_date = Column(DateTime, nullable=False)
#     expiry_date = Column(DateTime, nullable=False)
#     status = Column(String, default="active")  # "active", "spent", "expired"
#     spent_on = Column(DateTime, nullable=True)
#     leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)


# class LeaveCoin(Base):
#     __tablename__ = "leave_coins"
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     grant_date = Column(DateTime, nullable=False)
#     expiry_date = Column(DateTime, nullable=False)
#     quantity = Column(Integer, nullable=False, default=1)
#     remaining = Column(Integer, nullable=False, default=1)
#     source = Column(String, nullable=False, default="monthly_grant")
#     created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
#     employee = relationship("Employee")
    
#     __table_args__ = (
#         Index("ix_leave_coins_employee_expiry", "employee_id", "expiry_date"),
#     )


# class LeaveCoinTxn(Base):
#     __tablename__ = "leave_coin_txn"
    
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     coin_id = Column(Integer, ForeignKey("leave_coins.id"), nullable=True)
#     type = Column(String, nullable=False)  # "grant" | "consume" | "expire" | "adjust" | "restore"
#     amount = Column(Integer, nullable=False)
#     ref_leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
#     occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
#     comment = Column(String, nullable=True)
    
#     employee = relationship("Employee")
#     coin = relationship("LeaveCoin")


# # ============================================================================
# # POST MODELS
# # ============================================================================

# class Post(Base):
#     __tablename__ = "posts"
    
#     id = Column(Integer, primary_key=True, index=True)
#     title = Column(Unicode(255), nullable=False)
#     content = Column(Unicode, nullable=False)
#     author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     is_pinned = Column(Boolean, default=False)
#     status = Column(String(20), default="published")
    
#     author = relationship("User", back_populates="posts")
#     reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")
#     views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")


# class PostReaction(Base):
#     __tablename__ = "post_reactions"
    
#     id = Column(Integer, primary_key=True, index=True)
#     post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     emoji = Column(Unicode(20), nullable=False)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
#     post = relationship("Post", back_populates="reactions")
#     user = relationship("User")
    
#     __table_args__ = (
#         UniqueConstraint('post_id', 'user_id', 'emoji', name='uc_post_user_emoji'),
#     )


# class PostView(Base):
#     __tablename__ = "post_views"
    
#     id = Column(Integer, primary_key=True, index=True)
#     post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     viewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
#     post = relationship("Post", back_populates="views")
#     user = relationship("User")
    
#     __table_args__ = (
#         UniqueConstraint('post_id', 'user_id', name='uc_post_user_view'),
#     )


# # ============================================================================
# # PASSWORD RESET TOKEN MODEL
# # ============================================================================

# class PasswordResetToken(Base):
#     """
#     Model for password reset tokens (OTP-based).
#     This table stores temporary OTP codes used for password reset.
#     """
#     __tablename__ = "password_reset_tokens"
    
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(
#         Integer,
#         ForeignKey("users.id", ondelete="CASCADE"),
#         nullable=False,
#         index=True
#     )
#     email = Column(String(255), nullable=False, index=True)
#     otp_code = Column(String(6), nullable=True, index=True)  # 6-digit OTP
#     token = Column(String(255), nullable=True, index=True)  # Future: URL-based token
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
#     expires_at = Column(DateTime, nullable=False, index=True)
#     is_used = Column(Boolean, default=False, nullable=False, index=True)
#     used_at = Column(DateTime, nullable=True)
#     ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
#     user_agent = Column(Text, nullable=True)  # Browser/device info
    
#     user = relationship("User", back_populates="password_reset_tokens")
    
#     def __repr__(self):
#         return f"<PasswordResetToken user_id={self.user_id} email={self.email} used={self.is_used}>"
    
#     def is_expired(self) -> bool:
#         """Check if this token has expired."""
#         return datetime.utcnow() > self.expires_at
    
#     def time_remaining(self) -> int:
#         """Get time remaining before expiry in seconds."""
#         if self.is_expired():
#             return 0
#         delta = self.expires_at - datetime.utcnow()
#         return int(delta.total_seconds())


# OLDEST MODELS FOR REFERENCE (TO BE REMOVED)
# from sqlalchemy import (
#     BigInteger,
#     Boolean,
#     Column,
#     DateTime,
#     Float,
#     ForeignKey,
#     Integer,
#     Index,
#     String,
#     Text,
#     UniqueConstraint,
#     Unicode,
#     func,
#     )
# from sqlalchemy.orm import relationship, DeclarativeBase
# from sqlalchemy.ext.declarative import declarative_base
# from datetime import datetime, timezone

# # TIMEZONE ARCHITECTURE NOTES:
# # =================================
# # - ALL DateTime fields in database store UTC time as naive datetime
# # - Use services.timezone_utils for IST conversion in API responses
# # - Database storage remains UTC for consistency, performance, and global compatibility


# class Base(DeclarativeBase):
#     pass

# class Role(Base):
#     """
#     Role lookup table for user authorization.
    
#     Provides hierarchical role management with levels:
#     - 0: employee (basic access)
#     - 50: admin (management access)
#     - 100: super_admin (full system access)
#     """
#     __tablename__ = 'roles'
    
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(50), unique=True, nullable=False, index=True)
#     display_name = Column(String(100), nullable=False)
#     description = Column(String(255), nullable=True)
#     level = Column(Integer, nullable=False, default=0)
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
#     # Relationship back to users
#     users = relationship("User", back_populates="role_rel")
    
#     def __repr__(self):
#         return f"<Role(id={self.id}, name='{self.name}', level={self.level})>"

# # class User(Base):
# #     __tablename__ = 'users'
# #     id = Column(Integer, primary_key=True, index=True)
# #     username = Column(String(15), unique=True, index=True)
# #     hashed_password = Column(String)
# #     role = Column(String, default="employee")  # "super_admin", "admin", "employee"
# #     posts = relationship("Post", back_populates="author")

# class TokenBlacklist(Base):
#     """
#     Track invalidated JWT tokens for logout functionality.
    
#     When a user logs out, their token's JTI is added here.
#     During authentication, tokens are checked against this table.
#     Expired tokens are periodically cleaned up.
#     """
#     __tablename__ = 'token_blacklist'
    
#     id = Column(Integer, primary_key=True, index=True)
#     jti = Column(String(50), unique=True, nullable=False, index=True)  # JWT ID from token
#     user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
#     username = Column(String(15), nullable=False)
#     blacklisted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     token_exp = Column(DateTime, nullable=False)  # When token would have expired naturally
#     reason = Column(String(50), default="user_logout")  # "user_logout", "admin_revoke", "security"
    
#     # Indexes for fast lookups
#     __table_args__ = (
#         Index('idx_blacklist_jti', 'jti'),
#         Index('idx_blacklist_user_id', 'user_id'),
#         Index('idx_blacklist_exp', 'token_exp'),
#     )
    
#     def __repr__(self):
#         return f"<TokenBlacklist(jti='{self.jti[:8]}...', user='{self.username}')>"

# class User(Base):
#     __tablename__ = 'users'
    
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String(15), unique=True, index=True)
#     email = Column(String(255), unique=True, index=True, nullable=False)
#     hashed_password = Column(String)
    
#     # Foreign key to roles table
#     role_id = Column(Integer, ForeignKey('roles.id'), nullable=True)
#     role = Column(String, default="employee")
#     # Relationship to Role table
#     role_rel = relationship("Role", back_populates="users")
    
#     posts = relationship("Post", back_populates="author")
    
#     password_reset_tokens = relationship(
#         "PasswordResetToken", 
#         back_populates="user", 
#         cascade="all, delete-orphan"
#     )
    
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
#     # Relationships
#     role_obj = relationship("Role", back_populates="users")
#     employee = relationship("Employee", back_populates="user", uselist=False)
#     blacklisted_tokens = relationship("TokenBlacklist", back_populates="user")

    
#     @property
#     def role_name(self) -> str:
#         if self.role_rel:
#             return self.role_rel.name
#         return self.role if self.role else "employee"
    
#     @property
#     def role_level(self) -> int:
#         if self.role_rel:
#             return self.role_rel.level
#         # Fallback mapping for old role column
#         role_map = {"employee": 0, "admin": 50, "super_admin": 100}
#         return role_map.get(self.role, 0)


# class Employee(Base):
#     __tablename__ = 'employees'
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String)
#     user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
#     email = Column(String, nullable=True)
#     phone = Column(String, nullable=True)
#     avatar_url = Column(String, nullable=True)
#     emp_code = Column(String, nullable=True)
#     user = relationship("User")
#     __table_args__ = (UniqueConstraint('user_id', name='_user_id_uc'),)

# class Attendance(Base):
#     __tablename__ = 'attendance'
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey('employees.id'))
#     login_time = Column(DateTime)
#     logout_time = Column(DateTime)
#     on_leave = Column(Boolean, default=False)
#     work_hours = Column(Float)

# class WorkSession(Base):
#     __tablename__ = "work_sessions"
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     clock_in_time = Column(DateTime, nullable=False)
#     clock_out_time = Column(DateTime, nullable=True)
#     status = Column(String, nullable=False, default="active")  # "active" | "break" | "ended"
#     total_work_seconds = Column(Integer, nullable=False, default=0)
    
#     daily_attendance_id = Column(Integer, ForeignKey('daily_attendance.id'), nullable=True)
#     daily_attendance = relationship("DailyAttendance", back_populates="work_sessions")
     
#     employee = relationship("Employee")

# # Update for Daily Attendance

# class DailyAttendance(Base):
#     """
#     Daily aggregated attendance for each employee.
#     Stores last 30 days of attendance data for fast access.
    
#     Replaces on-the-fly aggregation of work_sessions with pre-calculated daily totals.
#     Automatically created by nightly aggregation job at 2:00 AM IST.
#     """
#     __tablename__ = 'daily_attendance'
    
#     # Primary Key
#     id = Column(Integer, primary_key=True, index=True)
    
#     # Foreign Keys
#     employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    
#     # Date (unique per employee per day)
#     attendance_date = Column(DateTime, nullable=False)  # Stored as date, but DateTime for consistency
    
#     # Aggregated Metrics
#     total_work_seconds = Column(Integer, nullable=False, default=0)
#     total_break_seconds = Column(Integer, nullable=False, default=0)
#     session_count = Column(Integer, nullable=False, default=0)
    
#     # First and Last Times (for detailed display)
#     first_clock_in = Column(DateTime, nullable=True)
#     last_clock_out = Column(DateTime, nullable=True)
    
#     # Status: complete, partial, incomplete, absent, leave
#     status = Column(String(20), nullable=False, default='incomplete')
    
#     # Metadata
#     created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
#     # Relationships
#     employee = relationship("Employee")
#     work_sessions = relationship("WorkSession", back_populates="daily_attendance")
    
#     # Indexes (created in database migration)
#     __table_args__ = (
#         Index('idx_daily_attendance_date', 'attendance_date'),
#         Index('idx_daily_attendance_employee_date', 'employee_id', 'attendance_date'),
#         Index('idx_daily_attendance_status', 'status', 'attendance_date'),
#         UniqueConstraint('employee_id', 'attendance_date', name='unique_employee_date'),
#     )
    
#     def __repr__(self):
#         return f"<DailyAttendance(employee_id={self.employee_id}, date={self.attendance_date}, hours={self.total_work_seconds/3600:.2f})>"
    
#     @property
#     def total_work_hours(self) -> float:
#         """Convert work seconds to hours"""
#         return round(self.total_work_seconds / 3600, 2)
    
#     @property
#     def total_break_hours(self) -> float:
#         """Convert break seconds to hours"""
#         return round(self.total_break_seconds / 3600, 2)


# class ArchivedAttendance(Base):
#     """
#     Archived attendance data older than 30 days.
#     Stored for compliance and reporting (1 year retention).
    
#     Records are moved here from daily_attendance by nightly archival job.
#     Automatically deleted after 1 year to maintain database size.
#     """
#     __tablename__ = 'archived_attendance'
    
#     # Primary Key
#     id = Column(Integer, primary_key=True, index=True)
    
#     # Foreign Keys
#     employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    
#     # Date
#     attendance_date = Column(DateTime, nullable=False)
    
#     # Same Aggregated Data as DailyAttendance
#     total_work_seconds = Column(Integer, nullable=False)
#     total_break_seconds = Column(Integer, nullable=False)
#     session_count = Column(Integer, nullable=False)
#     first_clock_in = Column(DateTime, nullable=True)
#     last_clock_out = Column(DateTime, nullable=True)
#     status = Column(String(20), nullable=False)
    
#     # Archive Metadata
#     archived_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
#     original_daily_id = Column(Integer, nullable=True)  # Reference to original daily_attendance.id
    
#     # Relationships
#     employee = relationship("Employee")
    
#     # Indexes (fewer than daily_attendance - archive queries less frequent)
#     __table_args__ = (
#         Index('idx_archived_attendance_employee_date', 'employee_id', 'attendance_date'),
#         Index('idx_archived_attendance_date', 'attendance_date'),
#     )
    
#     def __repr__(self):
#         return f"<ArchivedAttendance(employee_id={self.employee_id}, date={self.attendance_date}, archived={self.archived_at})>"
    
#     @property
#     def total_work_hours(self) -> float:
#         """Convert work seconds to hours"""
#         return round(self.total_work_seconds / 3600, 2)
    
#     @property
#     def total_break_hours(self) -> float:
#         """Convert break seconds to hours"""
#         return round(self.total_break_seconds / 3600, 2)


# class BreakInterval(Base):
#     __tablename__ = "break_intervals"
#     id = Column(Integer, primary_key=True, index=True)
#     session_id = Column(Integer, ForeignKey("work_sessions.id"), index=True, nullable=False)
#     start_time = Column(DateTime, nullable=False)
#     end_time = Column(DateTime, nullable=True)

# class DailyQuote(Base):
#     __tablename__ = "daily_quotes"
#     id = Column(Integer, primary_key=True, index=True)
#     date_utc = Column(DateTime, unique=True, index=True, nullable=False)
#     text = Column(String, nullable=False)
#     author = Column(String, nullable=True)
    
# # class QuoteCategory(Base):
# #     __tablename__ = "quote_categories"
    
# #     id = Column(Integer, primary_key=True, index=True)
# #     name = Column(String, unique=True, nullable=False)  # "motivation", "success", "leadership"
# #     description = Column(String, nullable=True)

# # class DailyQuote(Base):
# #     # Add category support
# #     category_id = Column(Integer, ForeignKey("quote_categories.id"), nullable=True)
# #     category = relationship("QuoteCategory")    

# class LeaveRequest(Base):
#     __tablename__ = "leave_requests"
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
#     start_date = Column(DateTime, nullable=False)
#     end_date = Column(DateTime, nullable=False)
#     leave_type = Column(String, nullable=False)
#     status = Column(String, default="pending")  # "pending", "approved", "denied"
#     reason = Column(String, nullable=True)
#     employee = relationship("Employee")

# class EmployeeCoin(Base):
#     __tablename__ = "employee_coins"
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
#     accrual_date = Column(DateTime, nullable=False)
#     expiry_date = Column(DateTime, nullable=False)
#     status = Column(String, default="active")  # "active", "spent", "expired"
#     spent_on = Column(DateTime, nullable=True)
#     leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)

# class LeaveCoin(Base):
#     __tablename__ = "leave_coins"
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     grant_date = Column(DateTime, nullable=False)
#     expiry_date = Column(DateTime, nullable=False)
#     quantity = Column(Integer, nullable=False, default=1)
#     remaining = Column(Integer, nullable=False, default=1)
#     source = Column(String, nullable=False, default="monthly_grant")
#     created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
#     employee = relationship("Employee")
    
#     __table_args__ = (
#         Index("ix_leave_coins_employee_expiry", "employee_id", "expiry_date"),
#     )


# class LeaveCoinTxn(Base):
#     __tablename__ = "leave_coin_txn"
#     id = Column(Integer, primary_key=True, index=True)
#     employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
#     coin_id = Column(Integer, ForeignKey("leave_coins.id"), nullable=True)
#     type = Column(String, nullable=False)  # "grant" | "consume" | "expire" | "adjust" | "restore"
#     amount = Column(Integer, nullable=False)
#     ref_leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
#     occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
#     comment = Column(String, nullable=True)
#     employee = relationship("Employee")
#     coin = relationship("LeaveCoin")
    
    
# # POSTS
# class Post(Base):
#     __tablename__ = "posts"
    
#     id = Column(Integer, primary_key=True, index=True)
#     title = Column(Unicode(255), nullable=False)
#     content = Column(Unicode, nullable=False)  # Using String instead of Text for MSSQL compatibility
#     author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     is_pinned = Column(Boolean, default=False)
#     status = Column(String(20), default="published")
    
#     # Relationships
#     author = relationship("User", back_populates="posts")
#     reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")
#     views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")

# class PostReaction(Base):
#     __tablename__ = "post_reactions"
    
#     id = Column(Integer, primary_key=True, index=True)
#     post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     emoji = Column(Unicode(20), nullable=False)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
#     # Relationships
#     post = relationship("Post", back_populates="reactions")
#     user = relationship("User")
    
#     # Composite unique constraint
#     __table_args__ = (
#         UniqueConstraint('post_id', 'user_id', 'emoji', name='uc_post_user_emoji'),
#     )
    
# class PostView(Base):
#     __tablename__ = "post_views"
    
#     id = Column(Integer, primary_key=True, index=True)
#     post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     viewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
#     # Relationships
#     post = relationship("Post", back_populates="views")
#     user = relationship("User")
    
#     # Composite unique constraint
#     __table_args__ = (
#         UniqueConstraint('post_id', 'user_id', name='uc_post_user_view'),
#     )


# # PASSWORD RESET TOKEN MODEL
# # Purpose: Store OTP codes for password reset feature

# class PasswordResetToken(Base):
#     """
#     Model for password reset tokens (OTP-based).
    
#     This table stores temporary OTP codes used for password reset.
#     Each token:
#     - Is linked to a specific user
#     - Contains a 6-digit OTP code
#     - Expires after 15 minutes
#     - Can only be used once
#     - Tracks IP and user agent for security
    
#     Table name: password_reset_tokens
#     """
#     __tablename__ = "password_reset_tokens"
    
#     # Primary Key
#     id = Column(Integer, primary_key=True, index=True)
    
#     # User Information
#     user_id = Column(
#         Integer, 
#         ForeignKey("users.id", ondelete="CASCADE"),
#         nullable=False,
#         index=True
#     )
#     email = Column(String(255), nullable=False, index=True)
    
#     # Reset Methods
#     otp_code = Column(String(6), nullable=True, index=True)      # 6-digit OTP
#     token = Column(String(255), nullable=True, index=True)       # Future: URL-based token
    
#     # Timestamps
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
#     expires_at = Column(DateTime, nullable=False, index=True)
    
#     # Status
#     is_used = Column(Boolean, default=False, nullable=False, index=True)
#     used_at = Column(DateTime, nullable=True)
    
#     # Security Tracking
#     ip_address = Column(String(45), nullable=True)              # IPv4 or IPv6
#     user_agent = Column(Text, nullable=True)                    # Browser/device info
    
#     # Relationship to User
#     user = relationship("User", back_populates="password_reset_tokens")
    
#     def __repr__(self):
#         """String representation for debugging."""
#         return (
#             f"<PasswordResetToken("
#             f"id={self.id}, "
#             f"user_id={self.user_id}, "
#             f"email='{self.email}', "
#             f"otp_code='***{self.otp_code[-2:] if self.otp_code else 'None'}', "
#             f"expires_at={self.expires_at}, "
#             f"is_used={self.is_used}"
#             f")>"
#         )
    
#     def is_expired(self) -> bool:
#         """
#         Check if this token has expired.
        
#         Returns:
#             True if expired, False otherwise
#         """
#         return datetime.utcnow() > self.expires_at
    
#     def time_remaining(self) -> int:
#         """
#         Get time remaining before expiry in seconds.
        
#         Returns:
#             Seconds remaining (0 if expired)
#         """
#         if self.is_expired():
#             return 0
#         delta = self.expires_at - datetime.utcnow()
#         return int(delta.total_seconds())
