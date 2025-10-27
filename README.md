# Employee Management System - Backend API

> **Production-ready FastAPI backend for comprehensive employee management with attendance tracking, leave management, posts & reactions, and real-time notifications.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?style=flat)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
  - [Local Development](#local-development)
  - [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Authentication & Security](#authentication--security)
- [Timezone Handling](#timezone-handling)
- [Scheduled Tasks](#scheduled-tasks)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

This is the backend API for a comprehensive Employee Management System built with **FastAPI**. It provides RESTful endpoints for managing employees, attendance tracking, leave requests, announcements/posts, and real-time engagement metrics. The system is designed for medium-to-large organizations requiring robust workforce management with role-based access control.

### Key Capabilities

- **Employee Management**: CRUD operations for employee profiles with role-based permissions
- **Attendance System**: Check-in/check-out with location tracking, real-time attendance monitoring
- **Leave Management**: Request submission, approval workflow, leave coin balance tracking
- **Posts & Announcements**: Company-wide communication with reactions, views, and admin management
- **Real-time Dashboard**: Live attendance statistics, leave requests, and engagement metrics
- **Scheduled Jobs**: Automated daily tasks (quote rotation, leave coin allocation, attendance resets)

---

## ✨ Features

### Authentication & Authorization
- JWT-based stateless authentication with configurable expiry
- Role-based access control (Employee, Admin, Super Admin)
- Secure password hashing with bcrypt
- Token-based API protection on all sensitive endpoints

### Employee Management
- Employee profile creation and management
- Avatar upload and profile updates
- Employee code generation and tracking
- Admin-only employee CRUD operations
- Profile validation (email, phone number formats)

### Attendance Tracking
- **Real-time Check-in/Check-out**: Employees can mark attendance with location data
- **Attendance History**: Complete attendance logs with timestamps
- **Status Tracking**: Present, Absent, Half-day, Leave statuses
- **Admin Monitoring**: Real-time attendance dashboard with statistics
- **Daily Reset**: Automated attendance reset at midnight IST

### Leave Management
- **Leave Request Workflow**: Employees submit requests with reason, dates, and type
- **Approval System**: Admin approval/rejection with remarks
- **Leave Coins**: Monthly coin allocation (2 coins/month) for casual/sick leave
- **Leave Types**: Casual Leave, Sick Leave, Earned Leave
- **Balance Tracking**: Real-time leave coin balance for each employee
- **Automated Allocation**: Monthly leave coin distribution via scheduler

### Posts & Announcements
- **Post Management**: Admin creates, pins, deletes company-wide posts
- **Reactions System**: Employees react with emojis (👍 ❤️ 😊 🎉 😮 😢)
- **View Tracking**: Post view counts and user engagement metrics
- **Detailed Analytics**: Admin sees who reacted, when, with which emoji
- **Unicode Support**: Proper emoji and multilingual text storage with NVARCHAR

### Dashboard & Insights
- **Admin Dashboard**: Real-time statistics (total employees, present count, leave requests)
- **Attendance Metrics**: Today's attendance percentage, department-wise breakdown
- **Leave Analytics**: Pending requests, approved/rejected counts
- **Post Engagement**: Top reacted posts, most viewed announcements

### Timezone Support
- **IST-first Design**: All timestamps stored and displayed in Indian Standard Time
- **Consistent Formatting**: Standardized datetime handling across all modules
- **Localized Scheduling**: Jobs run at IST midnight (leave allocation, attendance reset)

---

## 🛠️ Technology Stack

### Core Framework
- **FastAPI** 0.104.1 - Modern, high-performance web framework
- **Uvicorn** - Lightning-fast ASGI server
- **Python** 3.11+ - Latest stable Python version

### Database & ORM
- **SQLAlchemy** 2.0+ - Powerful ORM with async support
- **Microsoft SQL Server** - Production database (NVARCHAR for Unicode)
- **PyODBC** - SQL Server connectivity with ODBC Driver 18

### Authentication & Security
- **python-jose** - JWT token generation and validation
- **passlib[bcrypt]** - Secure password hashing
- **python-dotenv** - Environment variable management

### Background Jobs
- **APScheduler** - Scheduled task management (cron jobs)
- Automated daily tasks (leave coins, attendance reset, quote rotation)

### Utilities
- **Pydantic** - Data validation and serialization
- **pytz** - Timezone conversions (UTC ↔ IST)
- **email-validator** - Email format validation

---

## 🏗️ Architecture

### Design Principles

**Separation of Concerns**
```
├── Routers       → API endpoints and request handling
├── Models        → Database schema (SQLAlchemy ORM)
├── Schemas       → Request/response validation (Pydantic)
├── Services      → Business logic (timezone, auth, scheduling)
├── Dependencies  → Shared utilities (auth, DB session)
└── Utils         → Helper functions
```

**RESTful API Design**
- Resource-based URLs (`/employees`, `/attendance`, `/leaves`, `/posts`)
- HTTP verbs (GET, POST, PUT, DELETE) for CRUD operations
- Consistent response format with status codes
- Pagination support on list endpoints

**Security-first Approach**
- JWT tokens with configurable expiry
- Role-based endpoint protection via dependencies
- SQL injection prevention (parameterized queries)
- Password complexity enforcement
- HTTPS-ready for production

**Timezone Consistency**
- All datetime operations use IST (Asia/Kolkata)
- UTC storage with IST formatting on response
- Scheduler jobs respect IST for daily tasks

---

## 📁 Project Structure

```
backend/
├── main.py                      # FastAPI app initialization, CORS, routers
├── db.py                        # Database connection and session management
├── models.py                    # SQLAlchemy ORM models (User, Employee, Post, etc.)
├── schemas.py                   # Pydantic validation schemas
├── auth.py                      # JWT authentication and password hashing
├── dependencies.py              # Shared dependencies (get_db, get_current_user, roles)
├── utils.py                     # Utility functions (UTC timezone handling)
│
├── routers/                     # API route modules
│   ├── attendance.py            # Employee attendance endpoints
│   ├── attendance_rt.py         # Real-time attendance (admin)
│   ├── leave.py                 # Leave request endpoints
│   ├── leave_coins.py           # Leave coin management
│   ├── employees.py             # Employee CRUD operations
│   ├── posts.py                 # Posts and reactions (employee)
│   ├── admin_posts.py           # Post management (admin)
│   └── inspiration.py           # Daily inspirational quotes
│
├── services/                    # Business logic modules
│   ├── timezone_utils.py        # IST datetime formatting
│   ├── quotes.py                # Quote rotation logic
│   ├── leave_coin.py            # Leave coin allocation logic
│   └── scheduler.py             # APScheduler job definitions
│
├── .env                         # Environment variables (DATABASE_URL, JWT_SECRET)
├── requirements.txt             # Python dependencies
├── gunicorn_conf.py            # Production server configuration
└── README.md                    # This file
```

### Key Files Explained

**`main.py`**
- FastAPI app instance with CORS middleware
- Router includes for all API modules
- Lifespan event for scheduler initialization
- Health check endpoint

**`models.py`**
- SQLAlchemy ORM models (User, Employee, Attendance, Leave, Post, etc.)
- Relationships (one-to-many, many-to-one)
- Unicode support (NVARCHAR for emoji/multilingual text)

**`schemas.py`**
- Pydantic models for request validation
- Response schemas with custom serializers
- Field validators (email, phone, password strength)

**`dependencies.py`**
- `get_db()`: Database session dependency
- `get_current_user()`: JWT token validation
- `allow_admin()`: Role-based access control

**`services/scheduler.py`**
- Daily midnight IST jobs:
  - Leave coin allocation (1st of every month)
  - Attendance status reset
  - Quote rotation

---

## 🚀 Installation

### Prerequisites

- **Python 3.11 or higher**
- **Microsoft SQL Server** (local or remote)
- **ODBC Driver 18 for SQL Server**
- **Git** (for cloning the repository)

### Local Development

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/employee-management-backend.git
cd employee-management-backend
```

#### 2. Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip wheel

# Install requirements
pip install -r requirements.txt
```

#### 4. Install ODBC Driver (if not already installed)

**Linux (Ubuntu/Debian):**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

**macOS:**
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18
```

**Windows:**
- Download from [Microsoft ODBC Driver Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

#### 5. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
# Or create manually:
nano .env
```

**`.env` file contents:**
```ini
# Database Configuration
DATABASE_URL=mssql+pyodbc://USERNAME:PASSWORD@HOST:PORT/DATABASE?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# Application Settings
APP_ENV=development
DEBUG=true
```

**⚠️ Important:** Replace database credentials with your actual SQL Server details.

#### 6. Initialize Database

Your database should already have the required tables. If migrating from scratch:

```python
# Run in Python console
from sqlalchemy import create_engine
from models import Base
from db import DATABASE_URL

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)
```

Or use Alembic for migrations (recommended for production).

#### 7. Run Development Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Will watch for changes in these directories: [...]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

#### 8. Verify Installation

Visit: `http://localhost:8000/docs`

You should see the **Swagger UI** interactive API documentation.

---

### Production Deployment

See the [Deployment Guide](#deployment) section for detailed production setup instructions including:
- AWS EC2 deployment
- Nginx reverse proxy configuration
- Systemd service setup
- HTTPS with Let's Encrypt
- Environment security

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | SQL Server connection string | - | ✅ |
| `JWT_SECRET_KEY` | Secret key for JWT signing | - | ✅ |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` | ✅ |
| `JWT_EXPIRE_MINUTES` | Token expiration time | `10080` (7 days) | ✅ |
| `APP_ENV` | Environment (`development`/`production`) | `development` | ❌ |
| `DEBUG` | Enable debug mode | `false` | ❌ |

### Database Connection String Format

```
mssql+pyodbc://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

**Example:**
```
mssql+pyodbc://sa:MyPassword123@localhost:1433/EmployeeDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

**For Azure SQL Database:**
```
mssql+pyodbc://admin@myserver:P@ssw0rd@myserver.database.windows.net:1433/EmployeeDB?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes
```

---

## 📚 API Documentation

### Interactive Documentation

Once the server is running, access:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Authentication Flow

1. **Login** - Get JWT token
```http
POST /auth/login
Content-Type: application/json

{
  "username": "john.doe",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

2. **Use Token** - Include in all subsequent requests
```http
GET /employees/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API Endpoints Overview

#### Authentication
- `POST /auth/login` - User login, returns JWT token

#### Employees
- `GET /employees/me` - Get current employee profile
- `PUT /employees/me` - Update current employee profile
- `GET /employees` - List all employees (Admin only)
- `POST /employees` - Create employee (Admin only)
- `PUT /employees/{id}` - Update employee (Admin only)
- `DELETE /employees/{id}` - Delete employee (Admin only)

#### Attendance
- `POST /attendance/check-in` - Employee check-in with location
- `POST /attendance/check-out` - Employee check-out
- `GET /attendance/my-attendance` - Get own attendance history
- `GET /admin/attendance/realtime` - Real-time attendance dashboard (Admin)
- `GET /admin/attendance/employee/{id}` - Employee attendance history (Admin)

#### Leaves
- `POST /leaves` - Submit leave request
- `GET /leaves/my-leaves` - Get own leave requests
- `GET /leaves/balance` - Get leave coin balance
- `PUT /leaves/{id}/approve` - Approve leave request (Admin)
- `PUT /leaves/{id}/reject` - Reject leave request (Admin)
- `GET /admin/leaves/pending` - Get pending leave requests (Admin)

#### Posts & Announcements
- `GET /posts` - Get all published posts
- `POST /posts/{id}/react` - React to post with emoji
- `POST /posts/{id}/view` - Mark post as viewed
- `GET /posts/unread-count` - Get unread posts count
- `POST /admin/posts` - Create post (Admin)
- `GET /admin/posts` - Get all posts with analytics (Admin)
- `DELETE /admin/posts/{id}` - Delete post (Admin)
- `POST /admin/posts/{id}/toggle-pin` - Pin/unpin post (Admin)

#### Quotes
- `GET /quote/today` - Get today's inspirational quote

---

## 🗄️ Database Schema

### Core Tables

#### `users`
- `id` (PK) - Auto-increment integer
- `username` (UNIQUE) - Login username
- `password` - Bcrypt hashed password
- `role` - Employee role (employee, admin, superadmin)
- `email` - Email address
- `phone` - Phone number
- `avatar_url` - Profile picture URL
- `emp_code` - Employee code
- `created_at` - Account creation timestamp

#### `employees`
- `id` (PK) - Auto-increment integer
- `user_id` (FK → users.id) - One-to-one with user
- `name` - Full name
- `email` - Work email
- `phone` - Contact number
- `avatar_url` - Profile picture
- `emp_code` - Employee code
- `created_at` - Record creation timestamp

#### `attendance`
- `id` (PK) - Auto-increment integer
- `employee_id` (FK → employees.id)
- `date` - Attendance date
- `status` - Attendance status (present, absent, leave, half_day)
- `check_in_time` - Check-in timestamp
- `check_out_time` - Check-out timestamp
- `location` - Check-in location (lat/long)
- `created_at` - Record creation

#### `leave_requests`
- `id` (PK) - Auto-increment integer
- `employee_id` (FK → employees.id)
- `leave_type` - Type of leave (casual, sick, earned)
- `start_date` - Leave start date
- `end_date` - Leave end date
- `reason` (NVARCHAR) - Leave reason
- `status` - Request status (pending, approved, rejected)
- `admin_remarks` (NVARCHAR) - Admin notes
- `created_at` - Request submission time

#### `leave_balance`
- `employee_id` (FK → employees.id)
- `leave_coins` - Available leave coins
- `last_updated` - Last coin update timestamp

#### `posts`
- `id` (PK) - Auto-increment integer
- `title` (NVARCHAR) - Post title (Unicode support)
- `content` (NVARCHAR) - Post content (Unicode support)
- `author_id` (FK → users.id)
- `is_pinned` - Pin to top flag
- `status` - Post status (published, draft)
- `created_at` - Post creation time
- `updated_at` - Last update time

#### `post_reactions`
- `id` (PK) - Auto-increment integer
- `post_id` (FK → posts.id)
- `user_id` (FK → users.id)
- `emoji` (NVARCHAR) - Emoji reaction (Unicode support)
- `created_at` - Reaction timestamp
- **Unique constraint:** (post_id, user_id, emoji) - One reaction per user per emoji

#### `post_views`
- `id` (PK) - Auto-increment integer
- `post_id` (FK → posts.id)
- `user_id` (FK → users.id)
- `viewed_at` - View timestamp

### Relationships

```
User (1) → (1) Employee
Employee (1) → (many) Attendance
Employee (1) → (many) LeaveRequest
Employee (1) → (1) LeaveBalance
User (1) → (many) Post (as author)
Post (1) → (many) PostReaction
Post (1) → (many) PostView
User (1) → (many) PostReaction
User (1) → (many) PostView
```

### Unicode Support

**All text fields that may contain emojis or multilingual content use `NVARCHAR`:**
- `posts.title`, `posts.content`
- `post_reactions.emoji`
- `leave_requests.reason`, `admin_remarks`

**Database Collation:** `Latin1_General_100_CI_AS_SC_UTF8` (SQL Server 2019+)

---

## 🔐 Authentication & Security

### JWT Token Flow

1. **User Login** → Server validates credentials
2. **Server** → Generates JWT token with user ID and role
3. **Client** → Stores token securely (mobile: FlutterSecureStorage)
4. **API Requests** → Include token in `Authorization: Bearer <token>` header
5. **Server** → Validates token, extracts user info, processes request

### Token Structure

```json
{
  "sub": "12345",           // User ID
  "role": "employee",       // User role
  "exp": 1730000000         // Expiration timestamp
}
```

### Password Security

- **Hashing Algorithm:** Bcrypt with salt
- **Minimum Length:** 8 characters (enforced in schemas)
- **Validation:** Letters, numbers, special chars recommended
- **Storage:** Only hashed passwords in database, never plaintext

### Role-Based Access Control

**Roles:**
- `employee` - Standard user (own data access)
- `admin` - Manager (read all, manage leaves, posts)
- `superadmin` - System admin (full CRUD on users/employees)

**Protection Mechanism:**
```python
@router.get("/admin/employees", dependencies=[Depends(allow_admin)])
def list_employees(db: Session = Depends(get_db)):
    # Only admin/superadmin can access
    ...
```

### Security Best Practices

✅ **Implemented:**
- JWT token expiration (configurable)
- Password hashing with bcrypt
- SQL injection prevention (parameterized queries via SQLAlchemy)
- CORS configuration for allowed origins
- HTTPS-ready (for production deployment)

⚠️ **Production Recommendations:**
- Use strong `JWT_SECRET_KEY` (min 32 chars, random)
- Enable HTTPS/TLS (Let's Encrypt on deployment)
- Restrict CORS origins to your domain only
- Set short token expiry for sensitive operations
- Implement token refresh mechanism (optional)
- Add rate limiting on login endpoint

---

## 🕐 Timezone Handling

### Design Philosophy

**All operations use Indian Standard Time (IST - Asia/Kolkata) as the canonical timezone.**

### Implementation Details

**Datetime Storage:**
- Database stores datetime **without timezone** (SQL Server `datetime` type)
- Application treats all stored times as IST
- No UTC conversion on storage

**Datetime Formatting:**
- All API responses format datetime strings using `services/timezone_utils.py`
- Format: `"2025-10-26 14:30:00"` (24-hour IST)
- No timezone suffix (implicitly IST)

**Scheduled Jobs:**
- APScheduler runs with IST timezone
- Daily jobs trigger at midnight IST (00:00:00 Asia/Kolkata)
- Jobs: leave coin allocation, attendance reset, quote rotation

**Utilities:**

```python
# services/timezone_utils.py

from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def format_ist_datetime(dt: datetime) -> str:
    """Convert datetime to IST string format"""
    if dt.tzinfo is None:
        # Assume stored datetime is IST
        ist_dt = IST.localize(dt)
    else:
        ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%Y-%m-%d %H:%M:%S")
```

**Example API Response:**
```json
{
  "id": 1,
  "employee_name": "John Doe",
  "check_in_time": "2025-10-26 09:15:00",  // IST
  "date": "2025-10-26"
}
```

---

## ⏰ Scheduled Tasks

### APScheduler Configuration

**Scheduler Type:** `BackgroundScheduler` (runs in separate thread)

**Timezone:** `Asia/Kolkata` (IST)

**Jobs:**

| Job | Schedule | Function | Description |
|-----|----------|----------|-------------|
| **Leave Coin Allocation** | 1st of month, 00:05 IST | `allocate_monthly_leave_coins()` | Add 2 leave coins to all employees |
| **Attendance Reset** | Daily, 00:01 IST | `reset_daily_attendance()` | Reset attendance status to "absent" for new day |
| **Quote Rotation** | Daily, 00:00 IST | `rotate_quote()` | Change daily inspirational quote |

### Job Details

#### 1. Leave Coin Allocation

**Trigger:** First day of every month at 00:05 IST

**Logic:**
- Fetch all employees from database
- Add 2 leave coins to each employee's balance
- Create `leave_balance` record if not exists
- Update `last_updated` timestamp

**Code:** `services/leave_coin.py`

#### 2. Attendance Reset

**Trigger:** Every day at 00:01 IST

**Logic:**
- Fetch employees without attendance record for today
- Create attendance records with status = "absent"
- Prevents null attendance on new day

**Code:** `services/scheduler.py`

#### 3. Quote Rotation

**Trigger:** Every day at 00:00 IST

**Logic:**
- Cycle through predefined inspirational quotes
- Store current quote index in global variable
- Return via `/quote/today` endpoint

**Code:** `services/quotes.py`

### Manual Job Execution (Development)

```python
# In Python console or debug script
from services.leave_coin import allocate_monthly_leave_coins
from services.scheduler import reset_daily_attendance
from services.quotes import rotate_quote

# Trigger jobs manually
allocate_monthly_leave_coins()
reset_daily_attendance()
rotate_quote()
```

---

## 🧪 Testing

### Manual Testing (Development)

Use the **Swagger UI** at `http://localhost:8000/docs` for interactive API testing.

**Steps:**
1. Click **"Authorize"** button
2. Login via `/auth/login` to get token
3. Copy token and paste in Authorization dialog
4. Test endpoints with sample data

### Automated Testing (Coming Soon)

**Recommended Stack:**
- `pytest` - Testing framework
- `httpx` - Async HTTP client
- `pytest-asyncio` - Async test support

**Test Coverage:**
- Unit tests for utility functions
- Integration tests for API endpoints
- Database transaction tests
- Authentication flow tests

**Example Test Structure:**
```
tests/
├── test_auth.py           # Login, token validation
├── test_employees.py      # Employee CRUD
├── test_attendance.py     # Attendance check-in/out
├── test_leaves.py         # Leave request workflow
└── test_posts.py          # Post creation, reactions
```

---

## 🚢 Deployment

### Production Deployment Guide

For detailed step-by-step production deployment on AWS EC2, see:
- [AWS EC2 Deployment Guide](DEPLOYMENT.md)
- [Production Configuration](docs/production-setup.md)

### Quick Production Checklist

**Before Deployment:**
- [ ] Update `JWT_SECRET_KEY` to strong random value
- [ ] Configure `DATABASE_URL` with production database
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Review CORS `allow_origins` (restrict to your domain)
- [ ] Ensure SQL Server allows inbound from deployment IP
- [ ] Create production `.env` file (never commit to Git)

**Deployment Steps:**
1. Launch EC2 instance (t2.micro free tier)
2. Install Python 3.11, Nginx, ODBC Driver
3. Clone repository to `/opt/app`
4. Create virtual environment, install dependencies
5. Configure systemd service for Gunicorn+Uvicorn
6. Set up Nginx reverse proxy
7. Obtain HTTPS certificate (Let's Encrypt)
8. Enable and start services

**Post-Deployment:**
- [ ] Test all endpoints via `https://yourdomain.com/docs`
- [ ] Verify scheduled jobs run correctly
- [ ] Set up CloudWatch logs and alarms
- [ ] Create database backup schedule
- [ ] Document rollback procedure

### Production Server Configuration

**Gunicorn Configuration** (`gunicorn_conf.py`):
```python
bind = "127.0.0.1:8000"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
accesslog = "-"
errorlog = "-"
```

**Systemd Service** (`/etc/systemd/system/fastapi.service`):
```ini
[Unit]
Description=Employee Management FastAPI Application
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/app
Environment="PATH=/opt/app/venv/bin"
EnvironmentFile=/opt/app/production.env
ExecStart=/opt/app/venv/bin/gunicorn -c /opt/app/gunicorn_conf.py main:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**Nginx Reverse Proxy** (`/etc/nginx/conf.d/app.conf`):
```nginx
upstream fastapi_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Error:** `Cannot connect to database / ODBC driver not found`

**Solution:**
- Verify ODBC Driver 18 is installed: `odbcinst -j`
- Check `DATABASE_URL` format is correct
- Test SQL Server connectivity: `telnet HOST PORT`
- Ensure SQL Server firewall allows inbound connections
- Verify username/password are correct

#### 2. Import Error: Module Not Found

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Verify Python version: `python --version` (should be 3.11+)

#### 3. JWT Token Invalid

**Error:** `401 Unauthorized / Could not validate credentials`

**Solution:**
- Check token hasn't expired (default 7 days)
- Verify `JWT_SECRET_KEY` matches between token generation and validation
- Ensure `Authorization: Bearer <token>` header is included
- Try logging in again to get fresh token

#### 4. Unicode Characters Show as '?'

**Error:** Emojis or special characters display as question marks

**Solution:**
- Verify database columns use `NVARCHAR` not `VARCHAR`
- Check database collation: `SELECT DATABASEPROPERTYEX(DB_NAME(), 'Collation')`
- Run SQL migrations to convert columns:
  ```sql
  ALTER TABLE posts ALTER COLUMN emoji NVARCHAR(20);
  ALTER TABLE posts ALTER COLUMN content NVARCHAR(MAX);
  ```
- Update SQLAlchemy models to use `Unicode` type

#### 5. Scheduled Jobs Not Running

**Error:** Leave coins not allocated / Quote doesn't change

**Solution:**
- Check scheduler initialized in `main.py` lifespan
- Verify server timezone: `timedatectl` (should be IST)
- Check logs for scheduler errors: `journalctl -u fastapi -f`
- Manually trigger jobs for testing (see Scheduled Tasks section)

#### 6. CORS Error from Frontend

**Error:** `Access-Control-Allow-Origin` blocked

**Solution:**
- Add frontend domain to CORS `allow_origins` in `main.py`:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://yourfrontend.com"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### Debugging Tips

**Enable Debug Logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check Server Logs:**
```bash
# Development
tail -f uvicorn.log

# Production (systemd)
sudo journalctl -u fastapi -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

**Test Database Connection:**
```python
from sqlalchemy import create_engine
from db import DATABASE_URL

engine = create_engine(DATABASE_URL)
conn = engine.connect()
print("✅ Database connected successfully")
conn.close()
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make changes** and commit (`git commit -m 'Add amazing feature'`)
4. **Push to branch** (`git push origin feature/amazing-feature`)
5. **Open Pull Request**

### Code Standards

- Follow PEP 8 style guide
- Write descriptive commit messages
- Add docstrings to new functions
- Update README if adding new features
- Test changes before submitting PR

### Pull Request Checklist

- [ ] Code follows project structure and naming conventions
- [ ] New endpoints documented in README
- [ ] Environment variables added to `.env.example`
- [ ] Database schema changes documented
- [ ] Tested manually via Swagger UI
- [ ] No hardcoded secrets or credentials

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

**Documentation:**
- API Docs: `https://your-domain.com/docs`
- ReDoc: `https://your-domain.com/redoc`

**Issues:**
- Report bugs via [GitHub Issues](https://github.com/your-org/employee-management-backend/issues)
- Feature requests welcome!

**Contact:**
- Email: dev@yourcompany.com
- Slack: #employee-management-dev

---

## 🙏 Acknowledgments

- **FastAPI** - Modern, high-performance web framework
- **SQLAlchemy** - Powerful ORM for Python
- **APScheduler** - Background job scheduling
- **Microsoft** - ODBC Driver for SQL Server
- **Community** - All contributors and testers

---

## 📊 Project Stats

- **Lines of Code:** ~5,000+
- **API Endpoints:** 30+
- **Database Tables:** 10
- **Scheduled Jobs:** 3
- **Dependencies:** 15+

---

**Built with ❤️ for efficient workforce management**

_Last Updated: October 26, 2025_
