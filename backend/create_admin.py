#!/usr/bin/env python3
"""
Create Admin User Script
Run this script to create an admin user in your database.

Usage:
    python create_admin.py <email> <password> [name]

Example:
    python create_admin.py admin@enzura.com mypassword123 "Admin User"
"""

import os
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlmodel import Session, select
from app.database import engine
from app.models import User
from app.auth import get_password_hash

# Load environment variables
try:
    load_dotenv(encoding="utf-8", override=True)
except Exception:
    try:
        load_dotenv()
    except Exception:
        pass

def create_admin_user(email, password, name="Admin User"):
    """Create an admin user"""
    if not engine:
        print("❌ Database not available!")
        print("   Make sure DATABASE_URL is set in Railway Variables")
        return False
    
    try:
        with Session(engine) as db:
            # Check if user already exists
            existing = db.exec(select(User).where(User.email == email)).first()
            if existing:
                print(f"⚠️  User with email {email} already exists!")
                print(f"   User ID: {existing.id}")
                print(f"   Role: {existing.role}")
                return False
            
            # Create admin user
            hashed_password = get_password_hash(password)
            admin_user = User(
                email=email,
                password_hash=hashed_password,
                name=name,
                role="ADMIN",
                client_id=None
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print("=" * 50)
            print("✅ Admin user created successfully!")
            print("=" * 50)
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Role: ADMIN")
            print(f"   User ID: {admin_user.id}")
            print("=" * 50)
            print("\n💡 You can now log in with these credentials!")
            return True
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password> [name]")
        print("\nExample:")
        print("  python create_admin.py admin@enzura.com mypassword123")
        print("  python create_admin.py admin@enzura.com mypassword123 'Admin User'")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Admin User"
    
    print("🚀 Creating admin user...")
    print("=" * 50)
    success = create_admin_user(email, password, name)
    
    if not success:
        sys.exit(1)

