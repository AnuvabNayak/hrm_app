from sqlalchemy import Float, Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

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
    __table_args__ = (UniqueConstraint('user_id', name='_user_id_uc'),)

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'))
    login_time = Column(DateTime)
    logout_time = Column(DateTime)
    on_leave = Column(Boolean, default=False)
    work_hours = Column(Float)
    # work_hours = Column(Integer)
    
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

# Leave Balance (additions)

class LeaveCoin(Base):
    __tablename__ = "leave_coins"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    grant_date = Column(DateTime, nullable=False)    # UTC
    expiry_date = Column(DateTime, nullable=False)   # UTC = grant_date + 12 months
    quantity = Column(Integer, nullable=False, default=1)
    remaining = Column(Integer, nullable=False, default=1)
    source = Column(String, nullable=False, default="monthly_grant")  # or "manual_adjustment"
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    employee = relationship("Employee")

Index("ix_leave_coins_employee_expiry", LeaveCoin.employee_id, LeaveCoin.expiry_date)

class LeaveCoinTxn(Base):
    __tablename__ = "leave_coin_txn"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    coin_id = Column(Integer, ForeignKey("leave_coins.id"), nullable=True)
    type = Column(String, nullable=False)  # "grant" | "consume" | "expire" | "adjust" | "restore"
    amount = Column(Integer, nullable=False)  # positive
    ref_leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    comment = Column(String, nullable=True)

    employee = relationship("Employee")
    coin = relationship("LeaveCoin")