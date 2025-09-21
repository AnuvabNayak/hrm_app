import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("MSSQL_DB_URL")

# Set up SQLAlchemy engine and session
# Add pool_pre_ping and pool_recycle to guard against stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    # Dependency to get a SQLAlchemy session.
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
# DATABASE_URL = os.getenv("MSSQL_DB_URL")

# # Set up SQLAlchemy engine and session
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def get_db():
#     # Dependency to get a SQLAlchemy session.
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()