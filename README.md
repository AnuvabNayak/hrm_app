# Human Resource Management (HRM) Backend – FastAPI

A robust, modular backend for managing users, employees, attendance, and leave in an HR system. Built with FastAPI, SQLAlchemy, and JWT authentication, this project is designed for scalability, security, and ease of integration with frontend teams.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Authentication \& Security](#authentication--security)
- [Database Models](#database-models)
- [Usage Examples](#usage-examples)
- [Development \& Testing](#development--testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)


## Features

- **User Authentication**: Secure JWT-based login and registration.
- **Role-Based Access Control**: Supports `super_admin`, `admin`, and `employee` roles.
- **Employee Management**: Full CRUD for employee records.
- **Attendance Tracking**: Log and manage attendance, with work hours calculation.
- **Leave Management**: Submit and manage leave requests.
- **OpenAPI/Swagger UI**: Interactive, auto-generated API documentation.
- **Environment-Based Configuration**: Secure handling of DB credentials and secrets.


## Project Structure

| File/Directory | Purpose/Contents |
| :-- | :-- |
| `main.py` | FastAPI app setup, routing, registration/login endpoints |
| `auth.py` | JWT authentication, password hashing, token logic |
| `db.py` | SQLAlchemy DB connection/session management |
| `models.py` | ORM models: User, Employee, Attendance, LeaveRequest |
| `schemas.py` | Pydantic schemas for request/response validation |
| `dependencies.py` | Dependency injection, role checks, user extraction |
| `employees.py` | Employee CRUD endpoints |
| `attendance.py` | Attendance endpoints |
| `leave.py` | Leave request endpoints |
| `requirements.txt` | Python dependencies |
| `.env` | Environment variables (DB URL, secret key) |
| `openapi.json` | OpenAPI schema (auto-generated) |
| `tests/` | Automated unit/integration tests (recommended) |

## Installation

1. **Clone the repository**

```bash
git clone https://github.com/AnuvabNayak/hrm_app.git
cd hrm_app
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```


## Configuration

1. **Environment Variables**

Create a `.env` file in the project root:

```
MSSQL_DB_URL="mssql+pyodbc://username:password@server/dbname?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
SECRET_KEY=your_secret_key
```

Replace with your actual credentials and a strong secret key.
2. **Database Setup**
    - Ensure your database is running and accessible.
    - Apply migrations or manually update the schema to match models (see troubleshooting for common issues).

## Running the Application

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

- Default: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)


## API Documentation

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)


## Authentication \& Security

- **JWT Authentication**
    - Obtain a token via `POST /token` with username and password.
    - Use the returned token as a Bearer token in the `Authorization` header for protected endpoints.
- **Role-Based Access**
    - `super_admin`, `admin`, `employee` roles enforced via dependencies.
    - Only authorized roles can access or modify sensitive resources.
- **Password Security**
    - Passwords are securely hashed using `bcrypt`.


## Database Models

| Model | Fields |
| :-- | :-- |
| **User** | `id`, `username`, `hashed_password`, `role` |
| **Employee** | `id`, `name`, `user_id` (foreign key to User) |
| **Attendance** | `id`, `employee_id`, `login_time`, `logout_time`, `on_leave`, `work_hours` |
| **LeaveRequest** | `id`, `employee_id`, `start_date`, `end_date`, `leave_type`, `status`, `reason` |

## Usage Examples

### Register a User

```json
POST /register
{
  "username": "johndoe",
  "password": "securepassword",
  "role": "employee"
}
```


### Obtain Access Token

Send `POST /token` with form data:

- `username`
- `password`

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "token_type": "bearer"
}
```


### Access Protected Endpoint

Add header:

```
Authorization: Bearer <access_token>
```


## Development

```bash
pytest
```

- **Code Quality**:
Follow PEP8 style guidelines and use docstrings for all modules, classes, and functions.
- **Async Support**:
Endpoints can be refactored to use `async def` for improved scalability.

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.


<div style="text-align: center">⁂</div>

[^1]: file.env

[^2]: auth.py

[^3]: db.py

[^4]: dependencies.py

[^5]: main.py

[^6]: models.py

[^7]: openapi.json

[^8]: requirements.txt

[^9]: schemas.py

[^10]: attendance.py

[^11]: employees.py

[^12]: leave.py

