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

### Step 2.4: Configure Root Directory

1. **Wait** for Railway to finish initial setup (30-60 seconds)
2. **Click** on your service (it will be named something like "enzura-ai" or "web")
3. **Click** the **"Settings"** tab (top menu)
4. **Scroll down** to **"Root Directory"**
5. **Click** the input field
6. **Type**: `backend`
7. **Click** **"Save"** (or it auto-saves)

### Step 2.5: Configure Start Command

1. **Still in Settings** tab
2. **Scroll down** to **"Start Command"**
3. **Click** the input field
4. **Type**:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. **Click** **"Save"** (or it auto-saves)

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

   **Variable 3: DATABASE_URL**
   - **Name**: `DATABASE_URL`
   - **Value**: Paste the URL you copied from Step 2.7
   - **Click** **"Add"**

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

### Step 2.9: Run Database Migration

1. **Click** on your **Postgres** database service
2. **Click** the **"Data"** tab
3. **Click** **"Query"** button
4. **Open** your local file: `backend/migrations/add_performance_indexes.sql`
5. **Copy** all the SQL content
6. **Paste** it into the Railway query editor
7. **Click** **"Run"** button
8. **Wait** for "Success" message ✅

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
3. **Add** `/api` at the end: `https://your-url.railway.app/api`
4. **Press Enter**
5. **You should see**: `{"message": "Enzura AI API is running!", ...}` ✅
6. **If you see an error**, check Railway logs (Step 2.12)

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

### Step 4.1: Update Backend CORS

1. **Go back** to Railway (in another tab)
2. **Click** on your main service (not Postgres)
3. **Click** **"Variables"** tab
4. **Find** `CORS_ORIGINS` variable
5. **Click** the **pencil icon** ✏️ to edit
6. **Change value** to your Vercel URL:
   - Example: `https://enzura-ai.vercel.app`
   - **Important**: Must match exactly (including `https://`)
7. **Click** **"Save"** (or it auto-saves)
8. **Railway will automatically redeploy** (takes 30-60 seconds)

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
3. **Click** "Tables"
4. **Should see** your database tables ✅
5. **If you created users**, you should see them in the `user` table

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

### Problem: Backend returns 500 Error

**Solution:**
1. Check Railway logs (Deployments tab → Latest deployment)
2. Common causes:
   - Missing environment variables
   - Database connection issue
   - Wrong `DATABASE_URL`

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

