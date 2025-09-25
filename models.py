from sqlalchemy import func, Float, Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime, timezone

# TIMEZONE ARCHITECTURE NOTES:
# =================================
# - ALL DateTime fields in database store UTC time as naive datetime
# - Use services.timezone_utils for IST conversion in API responses
# - Database storage remains UTC for consistency, performance, and global compatibility


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(15), unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="employee")  # "super_admin", "admin", "employee"

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    emp_code = Column(String, nullable=True)
    __table_args__ = (UniqueConstraint('user_id', name='_user_id_uc'),)

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
    status = Column(String, nullable=False, default="active")  # "active" | "break" | "ended"
    total_work_seconds = Column(Integer, nullable=False, default=0)
    employee = relationship("Employee")

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
    
# class QuoteCategory(Base):
#     __tablename__ = "quote_categories"
    
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, nullable=False)  # "motivation", "success", "leadership"
#     description = Column(String, nullable=True)

# class DailyQuote(Base):
#     # Add category support
#     category_id = Column(Integer, ForeignKey("quote_categories.id"), nullable=True)
#     category = relationship("QuoteCategory")    

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    leave_type = Column(String, nullable=False)
    status = Column(String, default="pending")  # "pending", "approved", "denied"
    reason = Column(String, nullable=True)
    employee = relationship("Employee")

class EmployeeCoin(Base):
    __tablename__ = "employee_coins"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    accrual_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    status = Column(String, default="active")  # "active", "spent", "expired"
    spent_on = Column(DateTime, nullable=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)

class LeaveCoin(Base):
    __tablename__ = "leave_coins"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    grant_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    remaining = Column(Integer, nullable=False, default=1)
    source = Column(String, nullable=False, default="monthly_grant")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    employee = relationship("Employee")

Index("ix_leave_coins_employee_expiry", LeaveCoin.employee_id, LeaveCoin.expiry_date)

class LeaveCoinTxn(Base):
    __tablename__ = "leave_coin_txn"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    coin_id = Column(Integer, ForeignKey("leave_coins.id"), nullable=True)
    type = Column(String, nullable=False)  # "grant" | "consume" | "expire" | "adjust" | "restore"
    amount = Column(Integer, nullable=False)
    ref_leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    comment = Column(String, nullable=True)
    employee = relationship("Employee")
    coin = relationship("LeaveCoin")