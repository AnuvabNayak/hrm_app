import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("MSSQL_DB_URL")

# ✅ MSSQL-COMPATIBLE ENGINE CONFIGURATION
engine = create_engine(
    DATABASE_URL,
    # ✅ EXISTING SETTINGS (KEEP THESE)
    pool_pre_ping=True,
    pool_recycle=1800,
    # ✅ REMOVE INVALID PARAMETERS FOR MSSQL
    # encoding='utf-8',  # ❌ NOT SUPPORTED FOR MSSQL
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
