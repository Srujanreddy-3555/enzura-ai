# 🔧 Fix: "Login Failed" Error

## ❌ The Problem

When you try to log in with admin credentials, you get:
```
Login failed
```

**This usually means**: There's no admin user in your database yet!

---

## ✅ Solution: Create an Admin User

Since this is a fresh database, you need to create your first admin user. Here are the methods:

---

## Method 1: Register via API (Easiest)

### Step 1: Use the Register Endpoint

You can create an admin user by calling the register API directly.

**Option A: Using Browser Console**

1. **Open** your Railway backend URL: `https://your-app.railway.app/docs`
2. **Find** the `/api/auth/register` endpoint
3. **Click** "Try it out"
4. **Fill in**:
   ```json
   {
     "email": "admin@enzura.com",
     "password": "your-secure-password",
     "name": "Admin User",
     "role": "ADMIN"
   }
   ```
5. **Click** "Execute"
6. **You should see** a success response with user details ✅

**Option B: Using curl (Terminal)**

```bash
curl -X POST "https://your-app.railway.app/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@enzura.com",
    "password": "your-secure-password",
    "name": "Admin User",
    "role": "ADMIN"
  }'
```

**Option C: Using Postman or Insomnia**

1. Create a POST request to: `https://your-app.railway.app/api/auth/register`
2. Set Content-Type: `application/json`
3. Body (JSON):
   ```json
   {
     "email": "admin@enzura.com",
     "password": "your-secure-password",
     "name": "Admin User",
     "role": "ADMIN"
   }
   ```
4. Send request

---

## Method 2: Create Admin User via Python Script

I'll create a script you can run to create an admin user.

### Step 1: Create the Script

Create a file `backend/create_admin.py`:

```python
import os
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlmodel import Session, select
from app.database import engine, get_db
from app.models import User
from app.auth import get_password_hash

# Load environment variables
load_dotenv()

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
            
            print(f"✅ Admin user created successfully!")
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Role: ADMIN")
            return True
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password> [name]")
        print("Example: python create_admin.py admin@enzura.com mypassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Admin User"
    
    create_admin_user(email, password, name)
```

### Step 2: Run the Script

**Using Railway CLI:**
```bash
railway run python backend/create_admin.py admin@enzura.com your-password
```

**Or locally (if DATABASE_URL is set):**
```bash
cd backend
python create_admin.py admin@enzura.com your-password
```

---

## Method 3: Direct Database Insert (Advanced)

If you have Railway CLI and can connect to the database:

1. **Connect to database:**
   ```bash
   railway connect postgres
   ```

2. **Insert admin user** (you'll need to hash the password first):
   ```sql
   -- First, get password hash (run this Python one-liner):
   -- python -c "from passlib.context import CryptContext; pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto'); print(pwd_context.hash('your-password'))"
   
   -- Then insert (replace HASHED_PASSWORD with output above):
   INSERT INTO "user" (email, password_hash, name, role, client_id, created_at)
   VALUES ('admin@enzura.com', 'HASHED_PASSWORD', 'Admin User', 'ADMIN', NULL, NOW());
   ```

**This method is more complex - use Method 1 or 2 instead!**

---

## ✅ After Creating Admin User

1. **Go to** your login page
2. **Enter** the email and password you just created
3. **Click** "Sign In"
4. **Should work!** ✅

---

## 🔍 Troubleshooting

### "Database not available" Error

**Fix:**
- Make sure `DATABASE_URL` is set in Railway Variables
- Check Railway logs to verify database connection
- See `FIX_DATABASE_CONNECTION.md`

### "Email already registered" Error

**Fix:**
- The user already exists
- Try logging in with that email
- Or use a different email

### "Incorrect email or password" After Creating User

**Fix:**
- Double-check email and password (case-sensitive)
- Make sure you're using the exact email you registered
- Check browser console (F12) for API errors

### API Returns 404

**Fix:**
- Check your Railway backend URL is correct
- Make sure `/api/auth/register` endpoint exists
- Verify backend is deployed and running

### CORS Error

**Fix:**
- Make sure `CORS_ORIGINS` in Railway includes your frontend URL
- Check both URLs use `https://`
- Wait for Railway to redeploy after updating CORS

---

## 📋 Quick Checklist

- [ ] Database is connected (check Railway logs)
- [ ] Admin user created (using one of the methods above)
- [ ] Can access `/api/auth/register` endpoint
- [ ] Login page loads correctly
- [ ] Enter correct email and password
- [ ] No CORS errors in browser console
- [ ] Backend URL is correct in frontend

---

## 💡 Recommended Method

**Use Method 1 (Register via API)** - it's the easiest:
1. Go to `https://your-app.railway.app/docs`
2. Use the `/api/auth/register` endpoint
3. Create admin user
4. Login with those credentials

**That's it!** ✅

---

**After creating the admin user, you should be able to log in successfully!**

