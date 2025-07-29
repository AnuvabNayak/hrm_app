from sqlalchemy import Float, Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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
