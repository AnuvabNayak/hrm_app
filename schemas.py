from pydantic import BaseModel, field_serializer, computed_field, Field, validator
from typing import Optional, Literal, List
from datetime import datetime
from utils import to_ist
import re
# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Employee schemas
class EmployeeCreate(BaseModel):
    name: str
    user_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    emp_code: Optional[str] = None

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
class LeaveRequestCreate(BaseModel):
    employee_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    leave_type: str
    reason: Optional[str] = None

class LeaveRequestUpdate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    leave_type: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None

class LeaveRequestOut(BaseModel):
    id: int
    employee_id: int
    start_date: datetime
    end_date: datetime
    leave_type: str
    status: str
    reason: Optional[str]

    @field_serializer("start_date")
    def serialize_start_date(self, value):
        return to_ist(value)

    @field_serializer("end_date")
    def serialize_end_date(self, value):
        return to_ist(value)

    class Config:
        from_attributes = True

# Leave Balance (additions)
class LeaveBalanceOut(BaseModel):
    available_coins: int
    raw_available: int
    expiring_soon: list[dict]
    recent_txns: list[dict]

    @field_serializer("expiring_soon")
    def serialize_expiry(self, v):
        from utils import to_ist
        out = []
        for item in v:
            out.append({
                "expiry_date": to_ist(item["expiry_date"]),
                "amount": item["amount"],
            })
        return out

    @field_serializer("recent_txns")
    def serialize_txns(self, v):
        out = []
        for t in v:
            out.append({
                "type": t["type"],
                "amount": t["amount"], 
                "occurred_at": t["occurred_at"],  # ✅ FIXED: Use string directly
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
