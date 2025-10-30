# HRM Backend Production Deployment Guide

**Complete FastAPI + PostgreSQL Deployment on AWS EC2**

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Phase 0: AWS EC2 Instance Setup](#phase-0-aws-ec2-instance-setup)
4. [Phase 1: Server Cleanup & System Preparation](#phase-1-server-cleanup--system-preparation)
5. [Phase 2: PostgreSQL Installation & Configuration](#phase-2-postgresql-installation--configuration)
6. [Phase 3: Application Deployment](#phase-3-application-deployment)
7. [Phase 4: Production Service Setup (Gunicorn + Systemd)](#phase-4-production-service-setup)
8. [Phase 5: Nginx Reverse Proxy](#phase-5-nginx-reverse-proxy)
9. [Phase 6: AWS Security Configuration](#phase-6-aws-security-configuration)
10. [Phase 7: Verification & Testing](#phase-7-verification--testing)
11. [Phase 8: Troubleshooting](#phase-8-troubleshooting)
12. [Phase 9: Maintenance & Operations](#phase-9-maintenance--operations)

---

## Overview

This guide documents the complete production deployment process for the HRM Backend application, from creating an AWS EC2 instance to a fully operational, production-ready FastAPI application with PostgreSQL database.

### Technology Stack

- **Server:** AWS EC2 t3.micro (Ubuntu 24.04 LTS)
- **Application:** FastAPI (Python 3.11)
- **Database:** PostgreSQL 16
- **WSGI Server:** Gunicorn with Uvicorn workers
- **Reverse Proxy:** Nginx
- **Process Manager:** Systemd
- **Scheduler:** APScheduler

### Architecture

```
Internet Users
     ↓
AWS Security Group (Firewall)
     ↓ Port 80 (HTTP)
EC2 Instance (Ubuntu 24.04)
     ↓
Nginx (Reverse Proxy)
     ↓ localhost:8000
Gunicorn (2 Workers)
     ↓
FastAPI Application
     ↓ localhost:5432
PostgreSQL 16 Database
```

---

## Prerequisites

### Required Resources

- AWS Account with EC2 access
- GitHub repository with backend code
- Basic Linux command line knowledge
- SSH client (PuTTY, Terminal, or AWS Instance Connect)

### Required Files

Your application should include:
- `main.py` - FastAPI application
- `models.py` - SQLAlchemy models
- `db.py` - Database configuration
- `requirements.txt` - Python dependencies
- `.env` - Environment variables
- `router/` - API route modules
- `services/` - Business logic modules

---

## Phase 0: AWS EC2 Instance Setup

### Step 0.1: Create EC2 Instance

1. **Login to AWS Console:** https://console.aws.amazon.com/ec2/

2. **Launch Instance:**
   - Click "Launch Instance"
   - Name: `hrm-backend-server`

3. **Choose AMI:**
   - Select: **Ubuntu Server 24.04 LTS**
   - Architecture: 64-bit (x86)

4. **Choose Instance Type:**
   - Select: **t3.micro** (1 vCPU, 1 GB RAM)
   - Suitable for: Small production apps, development

5. **Configure Key Pair:**
   - Create new key pair or use existing
   - Download `.pem` file (save securely!)

6. **Network Settings:**
   - Auto-assign public IP: **Enable**
   - Security group: Create new
   - Add rule: **SSH (22)** - Source: Your IP or 0.0.0.0/0

7. **Configure Storage:**
   - Size: **8 GB** (minimum)
   - Type: **gp3** (General Purpose SSD)

8. **Launch Instance**

### Step 0.2: Connect to Instance

**Note the Public IP address** (example: `3.111.58.29`)

**Via AWS Instance Connect:**
```bash
# Select instance → Connect → EC2 Instance Connect → Connect
```

**Via SSH (from local terminal):**
```bash
ssh -i /path/to/key.pem ubuntu@3.111.58.29
```

### Step 0.3: Initial Server Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y git curl wget nano htop net-tools

# Verify Ubuntu version
lsb_release -a
# Expected: Ubuntu 24.04 LTS

# Check system resources
free -h
df -h
```

---

## Phase 1: Server Cleanup & System Preparation

### Step 1.1: Remove Previous SQL Server Installation

```bash
# Stop MS SQL Server if running
sudo systemctl stop mssql-server 2>/dev/null || true

# Remove MS SQL Server packages
sudo apt remove -y mssql-server mssql-tools unixodbc-dev

# Remove MS SQL repository
sudo rm -f /etc/apt/sources.list.d/mssql-server.list
sudo rm -f /etc/apt/trusted.gpg.d/microsoft.gpg

# Clean package cache
sudo apt autoremove -y
sudo apt autoclean
```

### Step 1.2: Verify Cleanup

```bash
# Check no SQL Server processes
ps aux | grep -i mssql || echo "✅ No SQL Server processes"

# Reclaim disk space
df -h /
```

### Step 1.3: Install Python 3.11

```bash
# Install Python 3.11 and dependencies
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Verify installation
python3.11 --version
# Expected: Python 3.11.x

# Install pip for Python 3.11
sudo apt install -y python3-pip

# Upgrade pip
python3.11 -m pip install --upgrade pip
```

---

## Phase 2: PostgreSQL Installation & Configuration

### Step 2.1: Install PostgreSQL 16

```bash
# Install PostgreSQL 16 and extensions
sudo apt install -y postgresql postgresql-contrib

# Verify installation
psql --version
# Expected: psql (PostgreSQL) 16.x
```

### Step 2.2: Configure PostgreSQL

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Enable auto-start on boot
sudo systemctl enable postgresql

# Start PostgreSQL
sudo systemctl start postgresql
```

### Step 2.3: Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL prompt, run:
CREATE DATABASE hrm_db;
CREATE USER hrm_user WITH PASSWORD 'ZyTexa@0321';
GRANT ALL PRIVILEGES ON DATABASE hrm_db TO hrm_user;
ALTER DATABASE hrm_db OWNER TO hrm_user;

# Grant schema permissions
\c hrm_db
GRANT ALL ON SCHEMA public TO hrm_user;

# Exit PostgreSQL
\q
```

### Step 2.4: Test Database Connection

```bash
# Test connection
PGPASSWORD=ZyTexa@0321 psql -h localhost -U hrm_user -d hrm_db -c "SELECT version();"

# Expected: PostgreSQL 16.x version info
```

### Step 2.5: Configure PostgreSQL for Performance

```bash
# Edit PostgreSQL configuration (optional optimization)
sudo nano /etc/postgresql/16/main/postgresql.conf

# Recommended settings for t3.micro:
# shared_buffers = 128MB
# effective_cache_size = 512MB
# maintenance_work_mem = 64MB
# checkpoint_completion_target = 0.9
# wal_buffers = 16MB
# default_statistics_target = 100
# random_page_cost = 1.1

# Restart PostgreSQL to apply changes
sudo systemctl restart postgresql
```

---

## Phase 3: Application Deployment

### Step 3.1: Create Application Directory

```bash
# Create directory
sudo mkdir -p /opt/hrm-backend

# Set ownership
sudo chown -R ubuntu:ubuntu /opt/hrm-backend

# Navigate to directory
cd /opt/hrm-backend
```

### Step 3.2: Clone Application from GitHub

```bash
# Clone repository
git clone https://github.com/AnuvabNayak/hrm_app.git .

# Verify files
ls -la
# Expected: main.py, models.py, db.py, requirements.txt, router/, services/, etc.
```

### Step 3.3: Update Database Configuration

```bash
# Backup original db.py
cp db.py db.py.backup

# Edit db.py
nano db.py
```

**Replace with PostgreSQL configuration:**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set")

# PostgreSQL engine configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Step 3.4: Update Requirements for PostgreSQL

```bash
# Backup original
cp requirements.txt requirements.txt.backup

# Edit requirements.txt
nano requirements.txt
```

**Complete requirements.txt:**

```txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
sqlalchemy>=2.0.0
python-multipart>=0.0.9
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-decouple>=3.8
apscheduler>=3.10.0
requests>=2.31.0
pydantic>=2.3.0
gunicorn>=21.2.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
bcrypt>=4.0.0
pytz>=2024.1
```

### Step 3.5: Create Environment Configuration

```bash
# Create .env file
nano .env
```

**Environment variables:**

```env
# PostgreSQL Database Configuration
DATABASE_URL=postgresql://hrm_user:ZyTexa%400321@localhost/hrm_db

# JWT Configuration
SECRET_KEY=5bc3025337fb062e8bce0d6762c396f19c680d31317a3e3ee0177a5cff5acc70

# Application Configuration
ALLOWED_ORIGINS=http://3.111.58.29,http://localhost:5173
LOG_LEVEL=INFO
```

**Note:** `@` symbol in password is URL-encoded as `%40`

### Step 3.6: Create Logs Directory

```bash
mkdir -p logs
```

### Step 3.7: Create Python Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should change to: (venv) ubuntu@...
```

### Step 3.8: Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|sqlalchemy|psycopg2|uvicorn|gunicorn"
```

### Step 3.9: Create Database Tables

```bash
# Create all tables from models
python3.11 -c 'from db import engine; from models import Base; Base.metadata.create_all(bind=engine); print("Database tables created successfully")'

# Expected: Database tables created successfully
```

### Step 3.10: Verify Tables Created

```bash
# List all tables
PGPASSWORD=ZyTexa@0321 psql -h localhost -U hrm_user -d hrm_db -c "\dt"

# Expected: List of tables (users, employees, attendance, etc.)
```

### Step 3.11: Create Admin User

```bash
# Create admin user script
nano create_admin.py
```

**Admin user creation script:**

```python
from db import SessionLocal
from models import User, Employee
from auth import hash_password

db = SessionLocal()

try:
    # Check if admin exists
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Admin user already exists")
        print(f"Username: admin")
    else:
        # Create admin user
        admin_user = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            role="super_admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        # Create admin employee profile
        admin_emp = Employee(
            name="System Administrator",
            user_id=admin_user.id,
            email="admin@company.com",
            emp_code="EMP001"
        )
        db.add(admin_emp)
        db.commit()
        
        print("Admin user created successfully!")
        print(f"Username: admin")
        print(f"Password: admin123")
        print("Change password after first login!")
        
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
```

```bash
# Run admin creation script
python3.11 create_admin.py

# Expected: Admin user created successfully!
```

### Step 3.12: Test Application Manually

```bash
# Start uvicorn for testing
uvicorn main:app --host 0.0.0.0 --port 8000

# Expected output:
# INFO:     Started server process [xxxxx]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000

# Press Ctrl+C to stop
```

---

## Phase 4: Production Service Setup

### Step 4.1: Create Gunicorn Configuration

```bash
cd /opt/hrm-backend
nano gunicorn_config.py
```

**Gunicorn configuration:**

```python
import multiprocessing

# Server socket - bind to localhost only (Nginx will proxy)
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes (2 workers optimal for t3.micro)
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers after this many requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/opt/hrm-backend/logs/access.log"
errorlog = "/opt/hrm-backend/logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "hrm-backend"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None
```

### Step 4.2: Test Gunicorn

```bash
# Activate virtual environment
source venv/bin/activate

# Test gunicorn
gunicorn -c gunicorn_config.py main:app

# Expected:
# [2025-10-29 21:45:XX] [xxxxx] [INFO] Starting gunicorn
# [2025-10-29 21:45:XX] [xxxxx] [INFO] Listening at: http://127.0.0.1:8000
# [2025-10-29 21:45:XX] [xxxxx] [INFO] Using worker: uvicorn.workers.UvicornWorker

# Press Ctrl+C to stop
```

### Step 4.3: Create Systemd Service

```bash
sudo nano /etc/systemd/system/hrm-backend.service
```

**Systemd service configuration:**

```ini
[Unit]
Description=HRM FastAPI Backend Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/hrm-backend
Environment="PATH=/opt/hrm-backend/venv/bin"
ExecStart=/opt/hrm-backend/venv/bin/gunicorn -c gunicorn_config.py main:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 4.4: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service for auto-start
sudo systemctl enable hrm-backend

# Start service
sudo systemctl start hrm-backend

# Check status
sudo systemctl status hrm-backend

# Expected: Active: active (running)
```

### Step 4.5: Verify Service

```bash
# Check service is active
systemctl is-active hrm-backend

# Check port 8000 is listening
sudo ss -tlnp | grep 8000

# Test local connection
curl -I http://127.0.0.1:8000/docs

# Expected: HTTP/1.1 200 OK
```

---

## Phase 5: Nginx Reverse Proxy

### Step 5.1: Install Nginx

```bash
# Update package list
sudo apt update

# Install Nginx
sudo apt install -y nginx

# Verify installation
nginx -v

# Check status
sudo systemctl status nginx

# Expected: Active: active (running)
```

### Step 5.2: Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/hrm-backend
```

**Nginx configuration:**

```nginx
server {
    listen 80;
    server_name 3.111.58.29;

    client_max_body_size 50M;

    # Logging
    access_log /var/log/nginx/hrm-backend-access.log;
    error_log /var/log/nginx/hrm-backend-error.log;

    # Proxy to FastAPI application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Step 5.3: Enable Nginx Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/hrm-backend /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Expected: syntax is ok, test is successful
```

### Step 5.4: Restart Nginx

```bash
# Restart Nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx

# Verify port 80 is listening
sudo ss -tlnp | grep :80
```

### Step 5.5: Test Nginx Proxy

```bash
# Test local proxy
curl -I http://127.0.0.1/docs

# Expected: HTTP/1.1 200 OK
# Server: nginx/1.24.0
```

---

## Phase 6: AWS Security Configuration

### Step 6.1: Configure Security Group

1. **Go to AWS EC2 Console**
2. **Select your instance** → Security tab
3. **Click on Security Group** link
4. **Click "Edit inbound rules"**

### Step 6.2: Add HTTP Rule (Port 80)

**Add new rule:**
- Type: **HTTP**
- Port range: **80**
- Source: **0.0.0.0/0** (Anywhere IPv4)
- Description: `Nginx HTTP access`

**Add IPv6 rule:**
- Type: **HTTP**
- Port range: **80**
- Source: **::/0** (Anywhere IPv6)
- Description: `Nginx HTTP access IPv6`

### Step 6.3: Remove Port 8000 (Security)

**If port 8000 rule exists:**
- Find: Custom TCP, Port 8000
- Click: **Delete**
- Reason: Backend should only be accessible through Nginx

### Step 6.4: Save Security Group Rules

Click **"Save rules"**

**Final security group rules:**
| Type | Port | Source | Description |
|------|------|--------|-------------|
| SSH | 22 | 0.0.0.0/0 | SSH access |
| HTTP | 80 | 0.0.0.0/0 | Nginx HTTP |
| HTTP | 80 | ::/0 | Nginx HTTP IPv6 |

### Step 6.5: Test Browser Access

**Open browser and navigate to:**
```
http://3.111.58.29/docs
```

**Expected:** Swagger UI interface loads successfully

### Step 6.6: Test Login

In Swagger UI:
1. Find `POST /token`
2. Click "Try it out"
3. Enter: `username=admin`, `password=admin123`
4. Click "Execute"

**Expected:** Status 200 with JWT access token

---

## Phase 7: Verification & Testing

### Step 7.1: Complete System Status Check

```bash
echo "========================================" && \
echo "   HRM BACKEND SYSTEM STATUS REPORT    " && \
echo "========================================" && \
echo "" && \
echo "Date: $(date)" && \
echo "Server: $(hostname)" && \
echo "Uptime: $(uptime -p)" && \
echo "" && \
echo "--- SERVICE STATUS ---" && \
echo "PostgreSQL: $(systemctl is-active postgresql)" && \
echo "Backend Service: $(systemctl is-active hrm-backend)" && \
echo "Nginx: $(systemctl is-active nginx)" && \
echo "" && \
echo "--- LISTENING PORTS ---" && \
sudo ss -tlnp | grep -E ":(22|80|8000|5432)" && \
echo "" && \
echo "--- MEMORY USAGE ---" && \
free -h && \
echo "" && \
echo "--- DISK USAGE ---" && \
df -h / && \
echo "" && \
echo "========================================"
```

### Step 7.2: Test Authentication

```bash
# Test login endpoint
curl -X POST http://3.111.58.29/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# Expected: JSON with access_token
```

### Step 7.3: Test Protected Endpoints

```bash
# Get token
TOKEN=$(curl -s -X POST http://3.111.58.29/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Test protected endpoint
curl -X GET http://3.111.58.29/employees/me \
  -H "Authorization: Bearer $TOKEN"

# Expected: Admin employee data
```

### Step 7.4: Performance Test

```bash
# Response time test
for i in {1..5}; do
  time curl -s -o /dev/null -w "Response time: %{time_total}s\n" http://3.111.58.29/docs
done

# Expected: Response times under 1 second
```

### Step 7.5: Security Verification

```bash
# Verify port 8000 is NOT accessible externally
timeout 5 curl -I http://3.111.58.29:8000/docs 2>&1

# Expected: Connection timeout (this is good - means port is secured)

# Verify backend bound to localhost only
sudo ss -tlnp | grep 8000 | grep -q "127.0.0.1"

# Expected: Exit code 0 (confirmed localhost binding)
```

### Step 7.6: Database Connection Test

```bash
cd /opt/hrm-backend
source venv/bin/activate

python3 -c "
from db import SessionLocal
from models import User, Employee
db = SessionLocal()
try:
    print(f'Users: {db.query(User).count()}')
    print(f'Employees: {db.query(Employee).count()}')
    print('Database connection: SUCCESS')
finally:
    db.close()
"
```

### Step 7.7: Check Scheduled Jobs

```bash
# View scheduled job execution
sudo journalctl -u hrm-backend --since "24 hours ago" | grep -i "apscheduler" | tail -10

# Expected: Shows scheduled jobs executing
```

---

## Phase 8: Troubleshooting

### Common Issues and Solutions

#### Issue 1: Service Won't Start

**Symptoms:**
- `systemctl start hrm-backend` fails
- Service shows "inactive (dead)"

**Diagnosis:**
```bash
# Check detailed error logs
sudo journalctl -u hrm-backend -n 50 --no-pager

# Check if port is already in use
sudo ss -tlnp | grep 8000
```

**Solutions:**
```bash
# If port is in use by another process
sudo systemctl stop hrm-backend
sleep 2
sudo systemctl start hrm-backend

# If configuration error
cd /opt/hrm-backend
source venv/bin/activate
gunicorn -c gunicorn_config.py main:app  # Test manually
```

#### Issue 2: Database Connection Failed

**Symptoms:**
- Application logs show database errors
- "password authentication failed"

**Diagnosis:**
```bash
# Test PostgreSQL connection
PGPASSWORD=ZyTexa@0321 psql -h localhost -U hrm_user -d hrm_db -c "SELECT 1;"

# Check .env file
cat /opt/hrm-backend/.env | grep DATABASE_URL
```

**Solutions:**
```bash
# Verify password encoding in .env
# @ symbol must be encoded as %40
DATABASE_URL=postgresql://hrm_user:ZyTexa%400321@localhost/hrm_db

# Restart service after fixing
sudo systemctl restart hrm-backend
```

#### Issue 3: Nginx 502 Bad Gateway

**Symptoms:**
- Browser shows "502 Bad Gateway"
- Nginx error log shows connection refused

**Diagnosis:**
```bash
# Check if backend is running
sudo systemctl status hrm-backend

# Check if backend is listening
sudo ss -tlnp | grep 8000

# Check Nginx error logs
sudo tail -50 /var/log/nginx/hrm-backend-error.log
```

**Solutions:**
```bash
# Restart backend service
sudo systemctl restart hrm-backend

# Wait for service to fully start
sleep 5

# Restart Nginx
sudo systemctl restart nginx

# Test again
curl -I http://127.0.0.1/docs
```

#### Issue 4: High Memory Usage

**Symptoms:**
- Server becomes slow
- Out of memory errors

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check process memory
ps aux --sort=-%mem | head -10

# Check service memory
sudo systemctl status hrm-backend | grep Memory
```

**Solutions:**
```bash
# Reduce number of workers
nano /opt/hrm-backend/gunicorn_config.py
# Change: workers = 1  (from 2)

# Restart service
sudo systemctl restart hrm-backend

# Consider upgrading instance size if needed
# t3.micro (1GB) → t3.small (2GB)
```

#### Issue 5: Port 8000 Still Accessible Externally

**Symptoms:**
- Can access http://3.111.58.29:8000 from browser

**Diagnosis:**
```bash
# Check gunicorn binding
sudo ss -tlnp | grep 8000
# Should show 127.0.0.1:8000, NOT 0.0.0.0:8000
```

**Solutions:**
```bash
# Edit gunicorn config
nano /opt/hrm-backend/gunicorn_config.py

# Ensure binding is:
bind = "127.0.0.1:8000"  # NOT 0.0.0.0:8000

# Restart service
sudo systemctl restart hrm-backend

# Remove port 8000 from AWS Security Group
```

#### Issue 6: Scheduled Jobs Not Running

**Symptoms:**
- Expected scheduled tasks not executing

**Diagnosis:**
```bash
# Check for scheduler errors
sudo journalctl -u hrm-backend | grep -i "scheduler\|apscheduler"

# Check application startup logs
sudo tail -100 /opt/hrm-backend/logs/error.log
```

**Solutions:**
```bash
# Verify scheduler configuration in main.py
# Ensure APScheduler is properly initialized

# Restart service to reinitialize scheduler
sudo systemctl restart hrm-backend

# Monitor scheduler logs
sudo journalctl -u hrm-backend -f | grep apscheduler
```

### Emergency Procedures

#### Complete Service Restart

```bash
# Stop all services
sudo systemctl stop hrm-backend
sudo systemctl stop nginx
sudo systemctl stop postgresql

# Wait
sleep 5

# Start services in order
sudo systemctl start postgresql
sleep 2
sudo systemctl start hrm-backend
sleep 2
sudo systemctl start nginx

# Verify all running
sudo systemctl status postgresql hrm-backend nginx
```

#### Database Recovery

```bash
# Backup database first
pg_dump -h localhost -U hrm_user hrm_db > ~/hrm_backup_$(date +%Y%m%d).sql

# Restore from backup if needed
psql -h localhost -U hrm_user -d hrm_db < ~/hrm_backup_YYYYMMDD.sql
```

#### Application Rollback

```bash
cd /opt/hrm-backend

# View git history
git log --oneline -10

# Rollback to previous commit
git reset --hard <commit-hash>

# Restart service
sudo systemctl restart hrm-backend
```

---

## Phase 9: Maintenance & Operations

### Daily Operations

#### Check System Health

```bash
# Quick health check
sudo systemctl status hrm-backend nginx postgresql

# Memory and disk
free -h && df -h /

# Recent errors (if any)
sudo journalctl -u hrm-backend --since "1 hour ago" | grep -i error
```

#### Monitor Logs

```bash
# Follow backend logs
sudo journalctl -u hrm-backend -f

# Follow Nginx access logs
sudo tail -f /var/log/nginx/hrm-backend-access.log

# Follow application error logs
tail -f /opt/hrm-backend/logs/error.log
```

#### View Traffic Statistics

```bash
# Request count by status code
sudo tail -1000 /var/log/nginx/hrm-backend-access.log | awk '{print $9}' | sort | uniq -c | sort -rn

# Most accessed endpoints
sudo tail -1000 /var/log/nginx/hrm-backend-access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -10

# Unique visitors
sudo tail -1000 /var/log/nginx/hrm-backend-access.log | awk '{print $1}' | sort -u | wc -l
```

### Weekly Maintenance

#### System Updates

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Clean package cache
sudo apt autoremove -y
sudo apt autoclean

# Restart services if needed
sudo systemctl restart hrm-backend
```

#### Database Maintenance

```bash
# Vacuum database
sudo -u postgres psql -d hrm_db -c "VACUUM ANALYZE;"

# Check database size
sudo -u postgres psql -d hrm_db -c "SELECT pg_size_pretty(pg_database_size('hrm_db'));"

# Backup database
pg_dump -h localhost -U hrm_user hrm_db > ~/backups/hrm_backup_$(date +%Y%m%d).sql
```

#### Log Rotation

```bash
# Check log sizes
du -sh /var/log/nginx/*.log
du -sh /opt/hrm-backend/logs/*.log

# Manually rotate if needed
sudo logrotate -f /etc/logrotate.d/nginx

# Archive old application logs
cd /opt/hrm-backend/logs
gzip error.log.1 access.log.1
```

### Application Updates

#### Deploy New Code from GitHub

```bash
# Navigate to application directory
cd /opt/hrm-backend

# Backup current version
git branch backup-$(date +%Y%m%d)

# Pull latest code
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update dependencies (if requirements changed)
pip install -r requirements.txt

# Run any database migrations (if applicable)
# python3 manage.py migrate

# Restart service
sudo systemctl restart hrm-backend

# Monitor logs for errors
sudo journalctl -u hrm-backend -f
```

#### Update Python Dependencies

```bash
cd /opt/hrm-backend
source venv/bin/activate

# Update specific package
pip install --upgrade <package-name>

# Or update all packages (use with caution)
pip list --outdated
pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl restart hrm-backend
```

### Backup Procedures

#### Automated Backup Script

Create backup script:
```bash
nano ~/backup-hrm.sh
```

```bash
#!/bin/bash
# HRM Backend Backup Script

BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
echo "Backing up database..."
PGPASSWORD=ZyTexa@0321 pg_dump -h localhost -U hrm_user hrm_db > $BACKUP_DIR/db_backup_$DATE.sql

# Backup application files
echo "Backing up application files..."
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz /opt/hrm-backend --exclude=/opt/hrm-backend/venv --exclude=/opt/hrm-backend/logs

# Backup .env file
cp /opt/hrm-backend/.env $BACKUP_DIR/env_backup_$DATE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
```

```bash
# Make executable
chmod +x ~/backup-hrm.sh

# Run backup
~/backup-hrm.sh

# Schedule daily backup (cron)
crontab -e
# Add: 0 2 * * * /home/ubuntu/backup-hrm.sh >> /home/ubuntu/backup.log 2>&1
```

### Monitoring Setup

#### Create System Monitor Script

```bash
nano ~/monitor-hrm.sh
```

```bash
#!/bin/bash
# HRM Backend Monitoring Script

echo "=== HRM Backend Health Check ==="
echo "Time: $(date)"
echo ""

# Check services
echo "Services Status:"
echo "  PostgreSQL: $(systemctl is-active postgresql)"
echo "  Backend: $(systemctl is-active hrm-backend)"
echo "  Nginx: $(systemctl is-active nginx)"
echo ""

# Check resources
echo "Memory Usage:"
free -h | grep Mem | awk '{print "  Used: "$3" / "$2" ("$3/$2*100"%)"}'
echo ""

echo "Disk Usage:"
df -h / | tail -1 | awk '{print "  Used: "$3" / "$2" ("$5")"}'
echo ""

# Check recent errors
echo "Recent Errors (last 10 minutes):"
ERROR_COUNT=$(sudo journalctl -u hrm-backend --since "10 minutes ago" | grep -i error | wc -l)
echo "  Error count: $ERROR_COUNT"
echo ""

# Alert if services are down
if [ "$(systemctl is-active hrm-backend)" != "active" ]; then
    echo "ALERT: Backend service is DOWN!"
    # Send notification (email, Slack, etc.)
fi

echo "=== Health Check Complete ==="
```

```bash
# Make executable
chmod +x ~/monitor-hrm.sh

# Run every 5 minutes
crontab -e
# Add: */5 * * * * /home/ubuntu/monitor-hrm.sh >> /home/ubuntu/monitor.log 2>&1
```

### Performance Optimization

#### Enable Gzip Compression in Nginx

```bash
sudo nano /etc/nginx/nginx.conf
```

Add in `http` block:
```nginx
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;
```

```bash
# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

#### Optimize PostgreSQL

```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
```

For t3.micro (1GB RAM):
```conf
shared_buffers = 256MB
effective_cache_size = 512MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2MB
min_wal_size = 1GB
max_wal_size = 4GB
```

```bash
# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Security Hardening

#### Update Admin Password

```bash
cd /opt/hrm-backend
source venv/bin/activate

python3 -c "
from db import SessionLocal
from models import User
from auth import hash_password

db = SessionLocal()
try:
    admin = db.query(User).filter(User.username == 'admin').first()
    if admin:
        admin.hashed_password = hash_password('NEW_SECURE_PASSWORD')
        db.commit()
        print('Admin password updated')
finally:
    db.close()
"
```

#### Configure Firewall (UFW)

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS (for future SSL)
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

#### Regular Security Updates

```bash
# Enable automatic security updates
sudo apt install -y unattended-upgrades

# Configure
sudo dpkg-reconfigure -plow unattended-upgrades
```

### Documentation

#### Service Management Commands

**Start/Stop/Restart:**
```bash
sudo systemctl start hrm-backend
sudo systemctl stop hrm-backend
sudo systemctl restart hrm-backend
sudo systemctl reload hrm-backend  # Graceful restart
```

**Status and Logs:**
```bash
sudo systemctl status hrm-backend
sudo journalctl -u hrm-backend -f
sudo journalctl -u hrm-backend --since "1 hour ago"
sudo journalctl -u hrm-backend -n 100
```

**Nginx:**
```bash
sudo systemctl restart nginx
sudo systemctl reload nginx
sudo nginx -t  # Test configuration
```

**PostgreSQL:**
```bash
sudo systemctl status postgresql
sudo systemctl restart postgresql
sudo -u postgres psql  # Connect as postgres user
```

---

## Deployment Summary

### System Information

- **Server IP:** 3.111.58.29
- **OS:** Ubuntu 24.04 LTS
- **Instance Type:** AWS EC2 t3.micro
- **Region:** ap-south-1 (Mumbai)

### Access Information

- **API Documentation:** http://3.111.58.29/docs
- **API Base URL:** http://3.111.58.29
- **Admin Credentials:** admin / admin123

### File Locations

- **Application:** `/opt/hrm-backend/`
- **Virtual Environment:** `/opt/hrm-backend/venv/`
- **Environment Config:** `/opt/hrm-backend/.env`
- **Gunicorn Config:** `/opt/hrm-backend/gunicorn_config.py`
- **Systemd Service:** `/etc/systemd/system/hrm-backend.service`
- **Nginx Config:** `/etc/nginx/sites-available/hrm-backend`
- **Application Logs:** `/opt/hrm-backend/logs/`
- **Nginx Logs:** `/var/log/nginx/hrm-backend-*.log`

### Database Information

- **Database Name:** hrm_db
- **Database User:** hrm_user
- **Database Password:** ZyTexa@0321
- **Connection String:** `postgresql://hrm_user:ZyTexa%400321@localhost/hrm_db`

### Port Configuration

| Port | Service | Access | Purpose |
|------|---------|--------|---------|
| 22 | SSH | Public | Server management |
| 80 | Nginx | Public | HTTP API access |
| 8000 | Gunicorn | Localhost | Backend application |
| 5432 | PostgreSQL | Localhost | Database |

### Service Configuration

- **Workers:** 2 Gunicorn workers
- **Worker Class:** uvicorn.workers.UvicornWorker
- **Auto-restart:** Enabled
- **Max Requests:** 1000 (worker restart)
- **Timeout:** 120 seconds

### Scheduled Jobs

1. **remove_old_attendance** - Cleanup old attendance records
2. **grant_monthly_coins** - Monthly leave coin allocation
3. **expire_old_coins** - Expire unused leave coins
4. **fetch_daily_quote_job** - Daily motivational quote (00:05 IST)

---

## Conclusion

This deployment guide has walked through the complete process of deploying a production-ready FastAPI application with PostgreSQL on AWS EC2. The system is now:

- ✅ **Secure** - Backend isolated, proper firewall rules
- ✅ **Stable** - Systemd auto-restart, proper error handling
- ✅ **Scalable** - Can handle concurrent requests efficiently
- ✅ **Monitored** - Comprehensive logging and monitoring
- ✅ **Maintainable** - Clear documentation and procedures

For any issues or questions, refer to the troubleshooting section or check service logs.

---

**Document Version:** 1.0  
**Last Updated:** October 30, 2025  
**Deployment Date:** October 29, 2025  
**Status:** Production Ready ✅
