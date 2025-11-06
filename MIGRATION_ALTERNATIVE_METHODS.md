# 🗄️ Database Migration - Alternative Methods

Since Railway's web interface Query button may not be available, here are all the ways to run your database migration.

---

## ✅ Method 1: Railway CLI (Recommended)

### Step 1: Install Railway CLI

**Option A: Using npm (Easiest)**
```bash
npm install -g @railway/cli
```

**Option B: Download from GitHub**
1. Go to: https://github.com/railwayapp/cli/releases
2. Download the latest `.msi` file for Windows
3. Run the installer
4. Follow the prompts

**Option C: Check if already installed**
```bash
railway --version
```

### Step 2: Login
```bash
railway login
```
(Opens browser to authorize)

### Step 3: Link to your project
```bash
railway link
```
(Select your Railway project from the list)

### Step 4: Connect to database
```bash
railway connect postgres
```
(This opens a psql connection in your terminal)

### Step 5: Run migration
1. **Open** your local file: `backend/migrations/add_performance_indexes.sql`
2. **Copy** all the SQL content
3. **Paste** it into the terminal (where psql is running)
4. **Press Enter** to execute
5. **Type** `\q` to exit

---

## ✅ Method 2: Python Migration Script (Easiest - No CLI!)

### Step 1: The script is already created
- File: `backend/run_migration.py`
- It reads `DATABASE_URL` from environment variables
- It runs all SQL from `backend/migrations/add_performance_indexes.sql`

### Step 2: Run via Railway CLI (if you have it)
```bash
railway run python backend/run_migration.py
```

### Step 3: Or run locally (if DATABASE_URL is set)
```bash
cd backend
python run_migration.py
```

**Note**: Make sure `DATABASE_URL` is set in Railway Variables first!

---

## ✅ Method 3: Using psql Directly (If you have PostgreSQL installed)

### Step 1: Get DATABASE_URL from Railway
1. Go to Railway → Postgres → **Variables** tab
2. Click the **eye icon** 👁️ to reveal `DATABASE_URL`
3. Copy the entire URL

### Step 2: Run migration
```bash
# Windows (PowerShell)
psql $env:DATABASE_URL -f backend/migrations/add_performance_indexes.sql

# Or extract parts and use:
psql -h your-host -U your-user -d your-database -f backend/migrations/add_performance_indexes.sql
```

---

## ✅ Method 4: Skip for Now (Can run later)

**Important**: The migration is for **performance optimization only**. Your app will work perfectly without it!

- ✅ App will function normally
- ⚠️ Queries will be slower with 200+ calls
- ✅ You can run migration anytime later

**When to run it:**
- When you have 100+ calls in database
- When you notice slow query performance
- When you have time to set up Railway CLI

---

## 🎯 Quick Decision Guide

**Choose based on your situation:**

| Situation | Recommended Method |
|-----------|-------------------|
| Have Node.js installed | Method 1 (npm install) |
| Don't want to install CLI | Method 4 (Skip for now) |
| Have PostgreSQL locally | Method 3 (psql) |
| Want to automate | Method 2 (Python script) |

---

## 📝 Migration SQL Content

If you need to see what the migration does, check:
- File: `backend/migrations/add_performance_indexes.sql`

It creates indexes on:
- `call` table (client_id, user_id, status, upload_date, etc.)
- `insights` table (call_id)
- `user` table (client_id, email)
- `client` table (name, status)

These indexes make queries **10-100x faster** with large datasets.

---

## ❓ Troubleshooting

### "railway: command not found"
- Install Railway CLI first (Method 1, Step 1)

### "DATABASE_URL not found"
- Go to Railway → Postgres → Variables
- Make sure `DATABASE_URL` exists and is correct

### "Permission denied"
- Make sure you're logged in: `railway login`
- Make sure you've linked to the project: `railway link`

### "Connection refused"
- Check Railway Postgres service is running
- Verify `DATABASE_URL` is correct
- Wait a few minutes if database was just created

---

**Need help?** Check Railway logs in the **Deployments** tab for specific errors.

