import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("MSSQL_DB_URL")

if not DATABASE_URL:
    raise RuntimeError("MSSQL_DB_URL environment variable is not set in .env file")

# ✅ MSSQL-COMPATIBLE ENGINE CONFIGURATION
engine = create_engine(
    DATABASE_URL,
    # Connection pool settings
    pool_pre_ping=True,        # Verify connections before using
    pool_recycle=1800,          # Recycle connections after 30 minutes
    echo=False,                 # Don't log SQL queries (set True for debugging)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency to get a SQLAlchemy session.
    Used with FastAPI Depends() for automatic session management.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# import os
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # DATABASE_URL = os.getenv("MSSQL_DB_URL")
# DATABASE_URL = os.getenv("DATABASE_URL")

# if not DATABASE_URL:
#     raise RuntimeError("DATABASE_URL environment variable not set")

# # ✅ MSSQL-COMPATIBLE ENGINE CONFIGURATION
# engine = create_engine(
#     DATABASE_URL,
#     pool_pre_ping=True,
#     pool_recycle=1800,
#     echo=False,
# )

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def get_db():
#     """Dependency to get a SQLAlchemy session."""
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
