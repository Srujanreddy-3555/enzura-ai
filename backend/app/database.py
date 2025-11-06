from sqlmodel import create_engine, Session, SQLModel
import os
from dotenv import load_dotenv

# Load environment variables with UTF-8 tolerance
try:
    load_dotenv(encoding="utf-8", override=True)
except Exception:
    try:
        load_dotenv()
    except Exception:
        pass

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Check if DATABASE_URL is valid (not placeholder)
if not DATABASE_URL or "xxx" in DATABASE_URL or "username:password" in DATABASE_URL:
    print("⚠️  DATABASE_URL not configured properly. Running in development mode without database.")
    engine = None
else:
    try:
        # Create engine
        # SECURITY: Disable SQL query logging in production
        echo_sql = os.getenv("ENVIRONMENT", "development") != "production"
        engine = create_engine(DATABASE_URL, echo=echo_sql)
        print("Database engine created successfully")
        # Ensure enums contain required values
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'client';")
                conn.commit()
        except Exception as enum_err:
            print(f"Enum check/update warning: {enum_err}")
    except Exception as e:
        print(f"Failed to create database engine: {e}")
        engine = None

def get_db():
    """Dependency to get database session"""
    if engine is None:
        print("Database not available - running in development mode")
        yield None
    else:
        with Session(engine) as session:
            yield session

def get_database_url():
    """Get the database URL from environment variables."""
    return DATABASE_URL

def create_tables():
    if engine is None:
        print("Cannot create tables - database not available")
        return False
    else:
        try:
            SQLModel.metadata.create_all(engine)
            return True
        except Exception as e:
            print(f"Failed to create tables: {e}")
            return False
