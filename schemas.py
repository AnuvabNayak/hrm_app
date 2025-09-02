from pydantic import BaseModel, field_serializer, computed_field
from typing import Optional
from datetime import datetime
from utils import to_ist

# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "employee"

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

class EmployeeUpdate(BaseModel):
    name: str = None

class EmployeeOut(BaseModel):
    id: int
    name: str
    user_id: int
    class Config:
        from_attributes = True

# Attendance schemas
class AttendanceCreate(BaseModel):
    employee_id: int
    login_time: datetime
    logout_time: datetime = None
    on_leave: bool = False
    work_hours: float = None

class AttendanceUpdate(BaseModel):
    login_time: datetime = None
    logout_time: datetime = None
    on_leave: bool = None
    work_hours: float = None

class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    login_time: datetime
    logout_time: Optional[datetime]
    on_leave: bool
    work_hours: float

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
        minutes = int(round((self.work_hours - hours) * 60))
        return f"{hours}h {minutes}m"

    class Config:
        from_attributes = True

# Leave request schemas
class LeaveRequestCreate(BaseModel):
    employee_id: int
    start_date: datetime
    end_date: datetime
    leave_type: str
    reason: str = None

class LeaveRequestUpdate(BaseModel):
    start_date: datetime = None
    end_date: datetime = None
    leave_type: str = None
    status: str = None
    reason: str = None

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
    available_coins: int          # min(rolling_available, 10)
    raw_available: int            # uncapped in rolling window
    expiring_soon: list[dict]     # [{ "expiry_date": datetime, "amount": int }]
    recent_txns: list[dict]       # last 10 txns: [{ "type": str, "amount": int, "occurred_at": datetime, "comment": Optional[str] }]

    @field_serializer("expiring_soon")
    def serialize_expiry(self, v):
        # convert datetimes to IST similar to others if desired
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
        from utils import to_ist
        out = []
        for t in v:
            out.append({
                "type": t["type"],
                "amount": t["amount"],
                "occurred_at": to_ist(t["occurred_at"]),
                "comment": t.get("comment"),
            })
        return out

    class Config:
        from_attributes = True