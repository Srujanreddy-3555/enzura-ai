# 🚀 Complete Step-by-Step Deployment Guide
## Frontend: Vercel | Backend: Railway

This guide walks you through **every single click** to deploy your app successfully.

---

## 📋 PRE-DEPLOYMENT CHECKLIST

Before starting, make sure you have:
- [ ] GitHub account (free)
- [ ] Vercel account (free, sign up with GitHub)
- [ ] Railway account (free, sign up with GitHub)
- [ ] OpenAI API key (for backend)
- [ ] Your code is working locally

---

## 🎯 PART 1: PREPARE YOUR CODE FOR GITHUB

### Step 1.1: Check if you have Git initialized

1. **Open** your terminal/command prompt
2. **Navigate** to your project folder:
   ```bash
   cd C:\Users\sruja\OneDrive\Desktop\Demo-mvp
   ```
3. **Check** if Git is initialized:
   ```bash
   git status
   ```
   - **If you see**: "fatal: not a git repository" → Go to Step 1.2
   - **If you see**: file list → Go to Step 1.3

### Step 1.2: Initialize Git (if needed)

1. **Run** in terminal:
   ```bash
   git init
   ```
2. **Add** all files:
   ```bash
   git add .
   ```
3. **Commit**:
   ```bash
   git commit -m "Initial commit - ready for deployment"
   ```

### Step 1.3: Create GitHub Repository

1. **Open** your browser
2. **Go to**: https://github.com
3. **Sign in** (or create account if needed)
4. **Click** the **"+"** icon in the top-right corner
5. **Click** **"New repository"**
6. **Fill in**:
   - **Repository name**: `enzura-ai` (or any name you like)
   - **Description**: "Enzura AI - Call Analytics Platform" (optional)
   - **Visibility**: Choose **Public** (free) or **Private** (if you have GitHub Pro)
   - **DO NOT** check "Add a README file"
   - **DO NOT** check "Add .gitignore"
   - **DO NOT** check "Choose a license"
7. **Click** the green **"Create repository"** button

### Step 1.4: Push Code to GitHub

1. **Copy** the commands from GitHub (they'll show after creating repo)
2. **In your terminal**, run:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/enzura-ai.git
   ```
   (Replace `YOUR_USERNAME` with your GitHub username)
3. **Run**:
   ```bash
   git branch -M main
   ```
4. **Run**:
   ```bash
   git push -u origin main
   ```
5. **Enter** your GitHub username and password (or use a Personal Access Token)
6. **Wait** for upload to complete
7. **Refresh** GitHub page - you should see all your files! ✅

---

## 🚂 PART 2: DEPLOY BACKEND ON RAILWAY

### Step 2.1: Sign Up for Railway

1. **Open** browser
2. **Go to**: https://railway.app
3. **Click** **"Start a New Project"** (or "Login" if you have an account)
4. **Click** **"Login with GitHub"**
5. **Authorize** Railway to access your GitHub
6. **You're now in Railway dashboard!** ✅

### Step 2.2: Create New Project

1. **Click** the **"New Project"** button (big blue button, top-left or center)
2. **You'll see** options:
   - "Deploy from GitHub repo" ← **Click this one**
   - "Empty Project"
   - "Deploy a Template"
3. **Click** **"Deploy from GitHub repo"**

### Step 2.3: Select Your Repository

1. **You'll see** a list of your GitHub repositories
2. **Find** `enzura-ai` (or whatever you named it)
3. **Click** on it
4. **Railway will start** deploying automatically! (You'll see a loading screen)
5. **⚠️ IMPORTANT**: The first deployment will likely FAIL - this is normal! We'll fix it in the next steps.

### Step 2.4: Configure Root Directory (CRITICAL - Do This First!)

1. **Wait** for Railway to finish initial setup (30-60 seconds)
2. **You'll see** an error like "Script start.sh not found" or "Railpack could not determine how to build" - **This is expected!**
3. **Click** on your service (it will be named something like "enzura-ai" or "web")
4. **Click** the **"Settings"** tab (top menu)
5. **Scroll down** to **"Root Directory"**
6. **Click** the input field
7. **Type**: `backend` (exactly this, no quotes, no slashes)
8. **Click** **"Save"** (or it auto-saves)
9. **Railway will automatically redeploy** - wait for it to complete (1-2 minutes)

### Step 2.5: Configure Start Command (If Still Needed)

1. **After** root directory is set and redeployed, check if it's working
2. **If still having issues**, go to **Settings** tab
3. **Scroll down** to **"Start Command"**
4. **Click** the input field
5. **Type** (or verify it says):
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. **Click** **"Save"** (or it auto-saves)
7. **Note**: Railway should auto-detect this from your `Procfile`, but setting it explicitly ensures it works

### Step 2.6: Add PostgreSQL Database

1. **Go back** to your project dashboard (click project name at top)
2. **Click** the **"New"** button (top-right, green button)
3. **Click** **"Database"**
4. **Click** **"Add PostgreSQL"**
5. **Wait** 10-20 seconds for database to be created
6. **You'll see** a new service appear called "Postgres" ✅

### Step 2.7: Get Database URL

1. **Click** on the **"Postgres"** service (the database you just created)
2. **Click** the **"Variables"** tab
3. **Look for** `DATABASE_URL` (it's automatically created)
4. **Click** the **eye icon** 👁️ next to `DATABASE_URL` to reveal it
5. **Click** the **copy icon** 📋 to copy the entire URL
6. **Save this somewhere** - you'll need it in the next step!

### Step 2.8: Add Environment Variables

1. **Go back** to your main service (click on "enzura-ai" or "web" service, not Postgres)
2. **Click** the **"Variables"** tab
3. **Click** **"New Variable"** button
4. **Add each variable one by one**:

   **Variable 1: OPENAI_API_KEY**
   - **Name**: `OPENAI_API_KEY`
   - **Value**: Your actual OpenAI API key (get from https://platform.openai.com/api-keys)
   - **Click** **"Add"**

   **Variable 2: OPENAI_MODEL**
   - **Name**: `OPENAI_MODEL`
   - **Value**: `gpt-4o`
   - **Click** **"Add"**

   **Variable 3: DATABASE_URL** ⚠️ **CRITICAL - This is the most important one!**
   - **Name**: `DATABASE_URL`
   - **Value**: Paste the URL you copied from Step 2.7
   - **⚠️ IMPORTANT**: Make sure you're adding this to your **main service** (not Postgres service)
   - **Click** **"Add"**
   - **Verify**: After adding, check that it appears in the Variables list

   **Variable 4: SECRET_KEY**
   - **Name**: `SECRET_KEY`
   - **Value**: Generate one by running this in terminal:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
     Copy the output and paste it here
   - **Click** **"Add"**

   **Variable 5: ENVIRONMENT**
   - **Name**: `ENVIRONMENT`
   - **Value**: `production`
   - **Click** **"Add"**

   **Variable 6: CORS_ORIGINS** (we'll update this later)
   - **Name**: `CORS_ORIGINS`
   - **Value**: `https://your-frontend.vercel.app` (we'll update this after frontend is deployed)
   - **Click** **"Add"**

5. **All variables added!** ✅

6. **⚠️ IMPORTANT: Trigger Redeploy**
   - Railway **usually** auto-redeploys when you add variables, but sometimes it doesn't
   - **Check** the **"Deployments"** tab - you should see a new deployment starting
   - **If no deployment started automatically**:
     - Go to **"Deployments"** tab
     - Click **"Redeploy"** button (or **"Deploy"** if available)
     - Or click the **three dots** (⋯) on the latest deployment → **"Redeploy"**
   - **Wait** 1-2 minutes for deployment to complete
   - **Check logs** to verify database connection works

### Step 2.9: Run Database Migration

**⚠️ IMPORTANT**: Railway's database UI may not show a Query button. Use one of these methods:

#### **Method 1: Using Railway CLI (Recommended - Easiest)**

1. **Install Railway CLI** (choose one method):

   **Option A: Using npm (Easiest - if you have Node.js installed)**
   ```bash
   npm install -g @railway/cli
   ```
   
   **Option B: Download from GitHub (Windows)**
   - Go to: https://github.com/railwayapp/cli/releases
   - Download the latest `.msi` file for Windows
   - Run the installer
   - Follow the installation prompts
   
   **Option C: Using PowerShell (Alternative)**
   ```powershell
   # First, check execution policy
   Get-ExecutionPolicy
   
   # If Restricted, allow scripts (run as Administrator):
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   
   # Then try installation (if URL works):
   irm https://railway.app/install.ps1 | iex
   ```
   
   **Option D: Mac/Linux**
   ```bash
   curl -fsSL https://railway.app/install.sh | sh
   ```
   
   **✅ Recommended**: Use **Option A (npm)** - it's the most reliable!

2. **Login to Railway**:
   ```bash
   railway login
   ```
   (Opens browser to authorize)

3. **Link to your project**:
   ```bash
   railway link
   ```
   (Select your project from the list)

4. **Connect to database**:
   ```bash
   railway connect postgres
   ```
   - **Wait** for the connection to establish (may take 10-20 seconds)
   - **You should see** a prompt like: `railway=#` or `postgres=#`
   - **⚠️ IMPORTANT**: If you see `PS C:\Users\...>` instead, you're still in PowerShell!
   - **If still in PowerShell**, the connection didn't work - try Method 4 (Python script) instead

5. **Run the migration** (ONLY if you see `railway=#` prompt):
   - **Open** your local file: `backend/migrations/add_performance_indexes.sql` (in Notepad, VS Code, or any text editor)
   - **Select all** the SQL content (Ctrl+A)
   - **Copy** it (Ctrl+C)
   - **Go back** to your terminal
   - **Make sure** you see `railway=#` or `postgres=#` (NOT `PS C:\Users\...>`)
   - **Right-click** in the terminal window and select **"Paste"** (or press Ctrl+V)
   - **Press Enter** to execute the SQL
   - You'll see messages like "CREATE INDEX" for each index created
   - **Wait** until you see the prompt again (like `railway=#`)
   - **Type** `\q` and press Enter to exit psql
   - You're done! ✅
   
   **⚠️ If you see PowerShell errors** (like "Missing expression after unary operator"), you're in PowerShell, not psql. Use Method 4 instead!

#### **Method 2: Using psql Directly (If you have PostgreSQL installed locally)**

1. **Get your DATABASE_URL**:
   - Go to Railway → Postgres → **Variables** tab
   - Copy the `DATABASE_URL` value (click eye icon to reveal)

2. **Run migration**:
   ```bash
   # Windows (PowerShell)
   $env:PGPASSWORD="your-password"; psql -h your-host -U your-user -d your-database -f backend/migrations/add_performance_indexes.sql
   
   # Mac/Linux
   psql $DATABASE_URL -f backend/migrations/add_performance_indexes.sql
   ```

#### **Method 3: Using Railway Web Interface (If Query button appears)**

1. **Click** on your **Postgres** database service
2. **Click** the **"Data"** tab
3. **Look for**:
   - **"Query"** button (if visible)
   - **"Connect"** button → **"Query"** option
   - **"SQL Editor"** or **"Run Query"** button
4. **If found**:
   - **Open** your local file: `backend/migrations/add_performance_indexes.sql`
   - **Copy** all the SQL content
   - **Paste** it into the query editor
   - **Click** **"Run"** or **"Execute"** button
   - **Wait** for "Success" message ✅

#### **Method 4: Using Python Script (EASIEST - Recommended if CLI paste doesn't work!)**

**This is the easiest method if `railway connect postgres` doesn't work!**

1. **The script is already created**: `backend/run_migration.py`
2. **Make sure it's in your GitHub repo**:
   ```bash
   git add backend/run_migration.py
   git commit -m "Add database migration script"
   git push
   ```
3. **Run it using Railway CLI**:
   ```bash
   railway run python backend/run_migration.py
   ```
   - This runs the script in Railway's environment
   - It automatically uses the `DATABASE_URL` from Railway variables
   - You'll see output like "✅ Migration completed successfully!"

4. **Or run it locally** (if you have DATABASE_URL set):
   ```bash
   cd backend
   python run_migration.py
   ```
   
   **✅ This is the recommended method if you got PowerShell errors!**

#### **Method 5: Skip for Now (Migration can run later)**

**Note**: The migration is for performance optimization. Your app will work without it, but queries will be slower with large datasets. You can run it later when the Query interface is available or using Method 1.

**✅ Recommended**: Use **Method 1 (Railway CLI)** - it's the most reliable way.

### Step 2.10: Get Your Backend URL

1. **Go back** to your main service (not Postgres)
2. **Click** the **"Settings"** tab
3. **Scroll down** to **"Domains"** section
4. **You'll see** a domain like: `https://enzura-ai-production.up.railway.app`
5. **Click** the **copy icon** 📋 next to the domain
6. **Save this URL** - you'll need it for frontend! ✅

### Step 2.11: Test Your Backend

1. **Open** a new browser tab
2. **Paste** your Railway URL (from Step 2.10)
3. **Test the root endpoint**: `https://your-url.railway.app/`
   - **Should see**: `{"message": "Enzura AI API is running!", ...}` ✅
4. **Test the API endpoint**: `https://your-url.railway.app/api`
   - **Should see**: `{"message": "Enzura AI API", "endpoints": {...}}` ✅
5. **Test health check**: `https://your-url.railway.app/health`
   - **Should see**: `{"status": "healthy", ...}` ✅
6. **⚠️ IMPORTANT**: Make sure your URL is `https://your-url.railway.app` (NOT `https://https://...`)
7. **If you see an error**, check Railway logs (Step 2.12)

### Step 2.12: Check Railway Logs (if needed)

1. **In Railway**, click on your service
2. **Click** the **"Deployments"** tab
3. **Click** on the latest deployment
4. **Scroll down** to see logs
5. **Look for** any red error messages
6. **Common issues**:
   - Missing environment variables → Add them in Variables tab
   - Database connection error → Check DATABASE_URL is correct
   - Import errors → Check Root Directory is set to `backend`

---

## 🌐 PART 3: DEPLOY FRONTEND ON VERCEL

### Step 3.1: Sign Up for Vercel

1. **Open** browser (new tab)
2. **Go to**: https://vercel.com
3. **Click** **"Sign Up"** (top-right)
4. **Click** **"Continue with GitHub"**
5. **Authorize** Vercel to access your GitHub
6. **You're now in Vercel dashboard!** ✅

### Step 3.2: Import Your Project

1. **Click** **"Add New Project"** button (big button, center or top)
2. **You'll see** your GitHub repositories
3. **Find** `enzura-ai` (or your repo name)
4. **Click** **"Import"** button next to it

### Step 3.3: Configure Project Settings

1. **Project Name**: Leave as is (or change if you want)
2. **Framework Preset**: Should auto-detect "Create React App" ✅
3. **Root Directory**: 
   - **Click** the input field
   - **Type**: `./frontend`
   - **OR** if you want to deploy from root, leave as `./`
4. **Build Command**: Should be `npm run build` ✅ (auto-filled)
5. **Output Directory**: Should be `build` ✅ (auto-filled)
6. **Install Command**: Should be `npm install` ✅ (auto-filled)

### Step 3.4: Add Environment Variable

1. **Before clicking Deploy**, click **"Environment Variables"** (expand it)
2. **Click** **"Add"** button
3. **Name**: `REACT_APP_API_URL`
4. **Value**: Your Railway backend URL + `/api`
   - Example: `https://enzura-ai-production.up.railway.app/api`
   - **Important**: Must include `/api` at the end!
5. **Select all environments**: 
   - ✅ Production
   - ✅ Preview
   - ✅ Development
6. **Click** **"Add"** button

### Step 3.5: Deploy!

1. **Scroll down** to bottom
2. **Click** the big blue **"Deploy"** button
3. **Wait** 2-3 minutes (you'll see build progress)
4. **Watch** the build logs:
   - Installing dependencies...
   - Building...
   - Build completed! ✅

### Step 3.6: Get Your Frontend URL

1. **After deployment completes**, you'll see:
   - **"Congratulations!"** message
   - A URL like: `https://enzura-ai.vercel.app`
2. **Click** the **copy icon** 📋 to copy the URL
3. **Save this URL** - you'll need it for backend CORS! ✅

### Step 3.7: Test Your Frontend

1. **Click** the **"Visit"** button (or open the URL in a new tab)
2. **You should see** your landing page! ✅
3. **Check browser console** (F12 → Console tab):
   - Should see no errors
   - If you see CORS errors, we'll fix that next

---

## 🔗 PART 4: CONNECT FRONTEND AND BACKEND

### Step 4.1: Update Backend CORS (CRITICAL - Fixes CORS Errors!)

1. **Go back** to Railway (in another tab)
2. **Click** on your main service (not Postgres)
3. **Click** **"Variables"** tab
4. **Find** `CORS_ORIGINS` variable
5. **Click** the **pencil icon** ✏️ to edit
6. **Change value** to your Vercel URL:
   - Example: `https://enzura-ai.vercel.app`
   - **Important**: Must match exactly (including `https://`)
   - **No trailing slash** (don't add `/` at the end)
7. **Click** **"Save"** (or it auto-saves)

8. **⚠️ CRITICAL: Trigger Redeploy**:
   - Railway **may** auto-redeploy, but **always verify**
   - Go to **"Deployments"** tab
   - **Check** if a new deployment started
   - **If not**, click **"Redeploy"** button
   - **Wait** 1-2 minutes for deployment to complete

9. **Verify** it worked:
   - Try logging in again
   - Check browser console (F12) - should see **no CORS errors** ✅
   - Login should work! ✅

### Step 4.2: Verify Connection

1. **Go back** to your Vercel frontend
2. **Open** browser console (F12 → Console)
3. **Try logging in** (or any API action)
4. **Check** Network tab (F12 → Network):
   - API calls should go to your Railway backend
   - Should see 200 status codes (green) ✅
   - No CORS errors ✅

---

## ✅ PART 5: FINAL TESTING

### Step 5.1: Test Landing Page

1. **Visit** your Vercel URL
2. **Should see** landing page with purple/blue gradients ✅
3. **Click** "Sign In" button
4. **Should navigate** to login page ✅

### Step 5.2: Test Login

1. **Enter** your credentials
2. **Click** "Login"
3. **Should redirect** to dashboard ✅
4. **Should see** your data loading ✅

### Step 5.3: Test API Calls

1. **Open** browser console (F12)
2. **Go to** Network tab
3. **Perform** any action (view calls, upload, etc.)
4. **Check** requests:
   - URL should be: `https://your-railway-url.railway.app/api/...`
   - Status should be: `200 OK` ✅
   - No CORS errors ✅

### Step 5.4: Test Database

1. **In Railway**, click on Postgres database
2. **Click** "Data" tab
3. **Click** "Tables" (if available)
4. **Should see** your database tables:
   - `user` - All users (Admin, Client, Rep)
   - `client` - Client companies
   - `sales_rep` - Sales representatives
   - `call` - Call records
   - `transcript` - Call transcripts
   - `insights` - AI-generated insights
5. **If you created users**, you should see them in the `user` table
6. **See** `DATABASE_TABLES_GUIDE.md` for detailed table information and how to view data

---

## 🐛 TROUBLESHOOTING

### Problem: Frontend shows "Network Error"

**Solution:**
1. Check `REACT_APP_API_URL` in Vercel includes `/api`
2. Verify Railway backend is running (check logs)
3. Check Railway URL is correct

### Problem: CORS Error in Browser

**Solution:**
1. Go to Railway → Variables
2. Check `CORS_ORIGINS` matches your Vercel URL exactly
3. Make sure both use `https://`
4. Wait for Railway to redeploy (30-60 seconds)

### Problem: "Script start.sh not found" or "Railpack could not determine how to build"

**Solution:**
1. **Go to** Railway → Your Service → Settings
2. **Set Root Directory** to: `backend` (exactly this, no quotes)
3. **Save** - Railway will auto-redeploy
4. **Verify** `Procfile` exists in `backend/` folder with: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Check** that `requirements.txt` exists in `backend/` folder
6. **Wait** for redeploy to complete (1-2 minutes)

### Problem: "Database not available for client monitoring" or Database Connection Fails

**Solution:**
1. **Check** `DATABASE_URL` exists in your **main service** Variables (not just Postgres)
2. **Verify** `DATABASE_URL` matches the Postgres service URL exactly
3. **Make sure** URL format is: `postgresql://user:password@host:port/database`
4. **Check** Railway Postgres service is running ("Deployment Online")
5. **Wait** 2-3 minutes after adding variable for redeploy
6. **Check logs** for: `Database engine created successfully` (should appear, not errors)
7. **See** `FIX_DATABASE_CONNECTION.md` for detailed troubleshooting

### Problem: Backend returns 500 Error

**Solution:**
1. Check Railway logs (Deployments tab → Latest deployment)
2. Common causes:
   - Missing environment variables (especially `DATABASE_URL`)
   - Database connection issue (see above)
   - Wrong `DATABASE_URL`
   - Root directory not set correctly

### Problem: "Login Failed" - Can't Log In

**Quick Diagnostic Steps:**

1. **Check Browser Console (F12 → Console)**:
   - Look for red error messages
   - Common: Network error, CORS error, 404, 401

2. **Check Network Tab (F12 → Network)**:
   - Try logging in
   - Find the `/api/auth/login` request
   - Check **Status Code**:
     - `200` = Success (frontend issue)
     - `401` = Wrong credentials
     - `404` = Wrong API URL
     - `CORS error` = CORS misconfiguration

3. **Verify User Exists**:
   - Use Railway CLI: `railway connect postgres`
   - Run: `SELECT * FROM "user";`
   - Should see your admin user

4. **Check Vercel Environment Variable**:
   - Go to Vercel → Settings → Environment Variables
   - Verify `REACT_APP_API_URL` = `https://your-app.railway.app/api`
   - **If missing or wrong**, add/update it and **redeploy Vercel**

5. **Test Login via API Docs**:
   - Go to `https://your-app.railway.app/docs`
   - Try `/api/auth/login` endpoint
   - If this works, issue is frontend connection
   - If this fails, issue is credentials/backend

6. **Check Railway CORS** (Most Common Issue!):
   - Railway → Variables → `CORS_ORIGINS`
   - Should include your Vercel URL exactly: `https://enzura-ai.vercel.app`
   - **If CORS error in console**, update `CORS_ORIGINS` and **redeploy**
   - **See** `FIX_CORS_ERROR.md` for detailed fix

**See** `DEBUG_LOGIN_ISSUE.md` for detailed step-by-step troubleshooting

### Problem: Database Migration Failed

**Solution:**
1. Go to Railway → Postgres → Data → Query
2. Run migration SQL again
3. Check for error messages
4. Make sure you're connected to the right database

### Problem: Frontend Build Failed on Vercel

**Solution:**
1. Check Vercel build logs
2. Common causes:
   - Missing `REACT_APP_API_URL`
   - Build errors in code
   - Wrong root directory

---

## 📋 QUICK REFERENCE

### Your URLs:
- **Frontend**: `https://your-app.vercel.app`
- **Backend**: `https://your-app.railway.app`
- **Backend API**: `https://your-app.railway.app/api`

### Environment Variables:

**Railway (Backend):**
```
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4o
DATABASE_URL=postgresql://... (from Railway)
SECRET_KEY=generated-key
ENVIRONMENT=production
CORS_ORIGINS=https://your-app.vercel.app
```

**Vercel (Frontend):**
```
REACT_APP_API_URL=https://your-app.railway.app/api
```

---

## 🎉 SUCCESS!

If everything works:
- ✅ Frontend loads on Vercel
- ✅ Backend responds on Railway
- ✅ Login works
- ✅ API calls succeed
- ✅ No console errors

**Your app is live!** 🚀

---

## 📞 NEED HELP?

1. **Check logs**:
   - Railway: Dashboard → Service → Deployments → Logs
   - Vercel: Dashboard → Project → Deployments → View Function Logs

2. **Common mistakes**:
   - Forgetting `/api` in `REACT_APP_API_URL`
   - Wrong CORS origins (must match exactly)
   - Database migration not run
   - Environment variables not set

3. **Test locally first**:
   - Backend: `cd backend && uvicorn app.main:app --reload`
   - Frontend: `cd frontend && npm start`
   - Verify everything works before deploying

---

**Follow these steps exactly, and you'll have your app deployed in ~30 minutes!** 🎯

