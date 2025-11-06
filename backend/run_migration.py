#!/usr/bin/env python3
"""
Database Migration Script
Run this script to apply performance indexes to your database.

Usage:
    python run_migration.py

Or set DATABASE_URL environment variable:
    DATABASE_URL=postgresql://... python run_migration.py
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
try:
    load_dotenv(encoding="utf-8", override=True)
except Exception:
    try:
        load_dotenv()
    except Exception:
        pass

def run_migration():
    """Run the database migration from SQL file"""
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set!")
        print("   Set it in Railway Variables or as an environment variable")
        sys.exit(1)
    
    if "xxx" in database_url or "username:password" in database_url:
        print("❌ ERROR: DATABASE_URL appears to be a placeholder!")
        print("   Please set a valid DATABASE_URL")
        sys.exit(1)
    
    # Get migration file path
    script_dir = Path(__file__).parent
    migration_file = script_dir / "migrations" / "add_performance_indexes.sql"
    
    if not migration_file.exists():
        print(f"❌ ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    # Read SQL file
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
    except Exception as e:
        print(f"❌ ERROR: Could not read migration file: {e}")
        sys.exit(1)
    
    # Connect to database
    try:
        print("🔌 Connecting to database...")
        engine = create_engine(database_url, echo=False)
        
        print("📝 Running migration...")
        with engine.connect() as conn:
            # Execute all SQL statements
            conn.execute(text(sql_content))
            conn.commit()
        
        print("✅ Migration completed successfully!")
        print("   Performance indexes have been created.")
        
    except Exception as e:
        print(f"❌ ERROR: Migration failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("🚀 Starting database migration...")
    print("=" * 50)
    run_migration()
    print("=" * 50)

