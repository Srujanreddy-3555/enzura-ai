# 🔧 Fix: PowerShell SQL Errors

## ❌ The Problem

You're seeing errors like:
```
Missing expression after unary operator '--'.
The term 'CREATE' is not recognized as a cmdlet...
```

**This means**: You're pasting SQL into **PowerShell**, not into **psql**!

## ✅ The Solution

You have **two options**:

---

## Option 1: Use Python Script (EASIEST - Recommended!)

This is the **easiest** method and doesn't require psql connection.

### Step 1: Make sure the script is in your repo
```bash
git add backend/run_migration.py
git commit -m "Add database migration script"
git push
```

### Step 2: Run it with Railway CLI
```bash
railway run python backend/run_migration.py
```

**That's it!** The script will:
- Connect to your Railway database automatically
- Run all the SQL statements
- Show you success messages

**Output you'll see:**
```
🚀 Starting database migration...
==================================================
🔌 Connecting to database...
📝 Running migration...
✅ Migration completed successfully!
   Performance indexes have been created.
==================================================
```

---

## Option 2: Fix the psql Connection

If `railway connect postgres` didn't work, try these steps:

### Step 1: Verify Railway CLI is installed
```bash
railway --version
```

### Step 2: Make sure you're logged in
```bash
railway login
```

### Step 3: Make sure you're linked to the project
```bash
railway link
```
(Select your Railway project)

### Step 4: Try connecting again
```bash
railway connect postgres
```

### Step 5: Check what you see

**✅ CORRECT - You're in psql:**
```
Connecting to postgres...
psql (14.x)
Type "help" for help.

railway=#  ← This is psql! Paste SQL here.
```

**❌ WRONG - You're still in PowerShell:**
```
PS C:\Users\sruja>  ← This is PowerShell! Don't paste SQL here.
```

**If you see PowerShell prompt**, the connection didn't work. Use **Option 1** instead!

---

## 🎯 Quick Decision

| Situation | What to Do |
|-----------|-----------|
| Got PowerShell errors | Use **Option 1** (Python script) |
| `railway connect postgres` shows `railway=#` | You can paste SQL there |
| `railway connect postgres` shows `PS C:\...>` | Use **Option 1** (Python script) |
| Want the easiest method | Use **Option 1** (Python script) |

---

## 💡 Why Option 1 is Better

1. ✅ **No psql connection needed**
2. ✅ **Works even if Railway CLI has issues**
3. ✅ **Automatic error handling**
4. ✅ **Clear success/failure messages**
5. ✅ **Uses Railway's DATABASE_URL automatically**

---

## 📝 What the Python Script Does

The script (`backend/run_migration.py`):
1. Reads `DATABASE_URL` from Railway environment variables
2. Connects to your PostgreSQL database
3. Reads the SQL from `backend/migrations/add_performance_indexes.sql`
4. Executes all SQL statements
5. Shows you success or error messages

**It's basically doing what you tried to do manually, but automatically!**

---

## ✅ Recommended Action

**Just run this one command:**
```bash
railway run python backend/run_migration.py
```

**That's it!** No need to mess with psql or PowerShell. 🎉

---

**Still having issues?** Check Railway logs in the **Deployments** tab for specific errors.

