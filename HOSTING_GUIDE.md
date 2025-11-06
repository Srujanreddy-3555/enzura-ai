# Complete Hosting Guide for Enzura AI

## 🏗️ Architecture Overview

Your application has **two parts** that need separate hosting:

1. **Frontend (React)** → Vercel (Recommended) ✅
2. **Backend (FastAPI)** → Railway, Render, or Fly.io (Recommended) ✅

**Why separate?**
- Frontend is static files (HTML, CSS, JS) → Perfect for Vercel
- Backend is a Python server → Needs a platform that runs Python

---

## 📦 Part 1: Frontend Hosting on Vercel

### Step 1: Prepare Your Frontend

1. **Create `.env` file** (for local testing):
   ```bash
   # In project root
   REACT_APP_API_URL=http://localhost:8000/api
   ```

2. **Test build locally**:
   ```bash
   npm install
   npm run build
   ```
   This creates a `build/` folder. Verify it works!

### Step 2: Push to GitHub

1. **Initialize Git** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Create GitHub repository**:
   - Go to https://github.com/new
   - Create a new repository (e.g., `enzura-frontend`)
   - **Don't** initialize with README

3. **Push your code**:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/enzura-frontend.git
   git branch -M main
   git push -u origin main
   ```

### Step 3: Deploy to Vercel

1. **Sign up for Vercel**:
   - Go to https://vercel.com
   - Sign up with GitHub (easiest way)

2. **Import your project**:
   - Click "Add New Project"
   - Select your GitHub repository (`enzura-frontend`)
   - Vercel will auto-detect it's a React app

3. **Configure build settings**:
   - **Framework Preset**: Create React App (auto-detected)
   - **Root Directory**: `./` (root)
   - **Build Command**: `npm run build` (auto-filled)
   - **Output Directory**: `build` (auto-filled)
   - **Install Command**: `npm install` (auto-filled)

4. **Add Environment Variables**:
   - Click "Environment Variables"
   - Add:
     ```
     Name: REACT_APP_API_URL
     Value: https://your-backend-domain.com/api
     ```
   - **Important**: Add this for all environments (Production, Preview, Development)

5. **Deploy**:
   - Click "Deploy"
   - Wait 2-3 minutes
   - Your app will be live at: `https://your-app.vercel.app`

### Step 4: Configure Custom Domain (Optional)

1. In Vercel dashboard → Settings → Domains
2. Add your domain (e.g., `app.enzura.com`)
3. Follow DNS instructions
4. Update `REACT_APP_API_URL` to match your backend domain

---

## 🚀 Part 2: Backend Hosting Options

### Option A: Railway (Recommended - Easiest) ⭐

**Why Railway?**
- ✅ Free tier available
- ✅ Automatic deployments from GitHub
- ✅ Built-in PostgreSQL database
- ✅ Environment variables management
- ✅ Very easy setup

#### Step-by-Step:

1. **Sign up**:
   - Go to https://railway.app
   - Sign up with GitHub

2. **Create new project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your backend repository

3. **Configure deployment**:
   - Railway auto-detects Python
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Railway provides `$PORT` automatically

4. **Add environment variables**:
   - Go to Variables tab
   - Add all variables from your `.env`:
     ```
     OPENAI_API_KEY=your-key
     OPENAI_MODEL=gpt-4o
     DATABASE_URL=your-database-url
     SECRET_KEY=your-secret-key
     ENVIRONMENT=production
     CORS_ORIGINS=https://your-frontend.vercel.app
     ```

5. **Add PostgreSQL database** (if needed):
   - Click "New" → "Database" → "PostgreSQL"
   - Railway creates database automatically
   - Copy the `DATABASE_URL` and add to environment variables

6. **Deploy**:
   - Railway auto-deploys on git push
   - Your API will be at: `https://your-app.railway.app`

7. **Run database migration**:
   - Go to your database → Connect
   - Run the migration SQL:
     ```sql
     -- Copy from: backend/migrations/add_performance_indexes.sql
     ```

---

### Option B: Render (Good Alternative)

**Why Render?**
- ✅ Free tier available
- ✅ Automatic SSL
- ✅ Easy setup

#### Step-by-Step:

1. **Sign up**: https://render.com

2. **Create new Web Service**:
   - Connect GitHub repository
   - Select your backend folder

3. **Configure**:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Add environment variables** (same as Railway)

5. **Add PostgreSQL database**:
   - Create new PostgreSQL database
   - Copy connection string to `DATABASE_URL`

---

### Option C: Fly.io (For More Control)

**Why Fly.io?**
- ✅ Global edge deployment
- ✅ More control over infrastructure
- ⚠️ Slightly more complex setup

#### Step-by-Step:

1. **Install Fly CLI**:
   ```bash
   # Windows (PowerShell):
   iwr https://fly.io/install.ps1 -useb | iex
   ```

2. **Sign up**: https://fly.io

3. **Login**:
   ```bash
   fly auth login
   ```

4. **Initialize in backend folder**:
   ```bash
   cd backend
   fly launch
   ```

5. **Create `fly.toml`** (auto-generated, but verify):
   ```toml
   app = "enzura-backend"
   primary_region = "iad"

   [build]

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0
     processes = ["app"]

   [[services]]
     http_checks = []
     internal_port = 8000
     processes = ["app"]
     protocol = "tcp"
     script_checks = []
   ```

6. **Set secrets**:
   ```bash
   fly secrets set OPENAI_API_KEY=your-key
   fly secrets set DATABASE_URL=your-database-url
   fly secrets set SECRET_KEY=your-secret-key
   fly secrets set ENVIRONMENT=production
   fly secrets set CORS_ORIGINS=https://your-frontend.vercel.app
   ```

7. **Deploy**:
   ```bash
   fly deploy
   ```

---

## 🔗 Part 3: Connect Frontend to Backend

### After Both Are Deployed:

1. **Get your backend URL**:
   - Railway: `https://your-app.railway.app`
   - Render: `https://your-app.onrender.com`
   - Fly.io: `https://your-app.fly.dev`

2. **Update Vercel environment variable**:
   - Go to Vercel → Your Project → Settings → Environment Variables
   - Update `REACT_APP_API_URL`:
     ```
     https://your-backend-domain.com/api
     ```
   - **Important**: Add `/api` at the end!

3. **Redeploy frontend**:
   - Vercel auto-redeploys when you push to GitHub
   - Or manually trigger: Deployments → Redeploy

4. **Update backend CORS**:
   - In backend environment variables, set:
     ```
     CORS_ORIGINS=https://your-frontend.vercel.app
     ```

---

## 🗄️ Part 4: Database Setup

### Option A: Use Railway/Render Database (Easiest)

Both Railway and Render offer built-in PostgreSQL:
- ✅ Automatic backups
- ✅ Easy connection
- ✅ Free tier available

### Option B: External Database (Neon, Supabase)

1. **Neon** (Recommended):
   - Go to https://neon.tech
   - Create free database
   - Copy connection string
   - Add to `DATABASE_URL` environment variable

2. **Supabase**:
   - Go to https://supabase.com
   - Create project
   - Get connection string from Settings → Database

### Run Migration:

After database is set up, run:
```sql
-- Connect to your database (via Railway dashboard, Neon SQL editor, etc.)
-- Run the migration:
-- Copy contents from: backend/migrations/add_performance_indexes.sql
```

---

## 📋 Complete Deployment Checklist

### Frontend (Vercel):
- [ ] Code pushed to GitHub
- [ ] Vercel project created
- [ ] Environment variable `REACT_APP_API_URL` set
- [ ] Build successful
- [ ] App accessible at Vercel URL
- [ ] Custom domain configured (optional)

### Backend (Railway/Render/Fly.io):
- [ ] Code pushed to GitHub
- [ ] Backend service created
- [ ] All environment variables set:
  - [ ] `OPENAI_API_KEY`
  - [ ] `OPENAI_MODEL`
  - [ ] `DATABASE_URL`
  - [ ] `SECRET_KEY`
  - [ ] `ENVIRONMENT=production`
  - [ ] `CORS_ORIGINS`
- [ ] Database created and connected
- [ ] Database migration run
- [ ] API accessible at backend URL
- [ ] API docs disabled (check `/docs` returns 404)

### Connection:
- [ ] Frontend `REACT_APP_API_URL` points to backend
- [ ] Backend `CORS_ORIGINS` includes frontend URL
- [ ] Test login works
- [ ] Test API calls work

---

## 🧪 Testing After Deployment

1. **Test Frontend**:
   - Visit your Vercel URL
   - Check console for errors
   - Test login

2. **Test Backend**:
   - Visit `https://your-backend.com/` (should return API info)
   - Visit `https://your-backend.com/docs` (should be 404 in production)
   - Test API endpoint: `https://your-backend.com/api/health` (if exists)

3. **Test Connection**:
   - Login from frontend
   - Check Network tab in browser DevTools
   - Verify API calls go to correct backend URL

---

## 🔧 Troubleshooting

### Frontend Issues:

**Problem**: API calls fail with CORS error
**Solution**: 
- Check `CORS_ORIGINS` in backend includes frontend URL
- Ensure frontend URL has `https://` not `http://`

**Problem**: Environment variable not working
**Solution**:
- Rebuild frontend after adding env vars
- Check variable name starts with `REACT_APP_`
- Redeploy in Vercel

### Backend Issues:

**Problem**: Database connection fails
**Solution**:
- Verify `DATABASE_URL` is correct
- Check database is accessible from hosting platform
- Ensure SSL is enabled in connection string

**Problem**: API returns 500 errors
**Solution**:
- Check backend logs (Railway/Render dashboard)
- Verify all environment variables are set
- Check `SECRET_KEY` is set and valid

**Problem**: Slow API responses
**Solution**:
- Run database migration (indexes)
- Check database connection pooling
- Verify `ENVIRONMENT=production` is set

---

## 💰 Cost Estimate

### Free Tier (Good for MVP):
- **Vercel**: Free (unlimited deployments)
- **Railway**: $5/month free credit (usually enough for MVP)
- **Render**: Free tier available (with limitations)
- **Neon Database**: Free tier (512 MB storage)

### Production (Recommended):
- **Vercel Pro**: $20/month (better performance)
- **Railway**: Pay-as-you-go (~$5-20/month)
- **Database**: Neon Pro ($19/month) or Supabase Pro ($25/month)

**Total**: ~$25-50/month for production

---

## 🎯 Recommended Setup for Your App

**Best for MVP/Testing:**
1. Frontend: Vercel (Free)
2. Backend: Railway (Free tier)
3. Database: Railway PostgreSQL (Free tier)

**Best for Production:**
1. Frontend: Vercel Pro ($20/month)
2. Backend: Railway (~$10/month)
3. Database: Neon Pro ($19/month)

---

## 📝 Quick Start Commands

### Railway (Recommended):

1. **Push backend to GitHub**
2. **Go to Railway.app** → New Project → Deploy from GitHub
3. **Add environment variables**
4. **Add PostgreSQL database**
5. **Deploy!**

### Vercel:

1. **Push frontend to GitHub**
2. **Go to Vercel.com** → Import Project
3. **Add `REACT_APP_API_URL` environment variable**
4. **Deploy!**

---

## 🆘 Need Help?

Common issues and solutions are in the Troubleshooting section above. If you encounter specific errors, check:
1. Backend logs (Railway/Render dashboard)
2. Frontend console (browser DevTools)
3. Network tab (check API requests)

---

**Last Updated**: After production optimization
**Status**: Ready for deployment

