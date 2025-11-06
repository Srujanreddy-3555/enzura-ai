# Quick Deployment Guide - Step by Step

## 🎯 Simplest Path: Vercel (Frontend) + Railway (Backend)

---

## 📦 STEP 1: Prepare Your Code

### 1.1 Separate Frontend and Backend (Optional but Recommended)

**Option A: Keep together (Easier for now)**
- Your current structure is fine
- Deploy frontend from root
- Deploy backend from `backend/` folder

**Option B: Split into two repos (Better for production)**
- Create `enzura-frontend` repo (just frontend code)
- Create `backend` repo (just backend code)

---

## 🚀 STEP 2: Deploy Backend First (Railway)

### 2.1 Push Backend to GitHub

```bash
# If not already a git repo:
cd backend
git init
git add .
git commit -m "Initial backend commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/enzura-backend.git
git push -u origin main
```

### 2.2 Deploy on Railway

1. **Go to**: https://railway.app
2. **Sign up** with GitHub
3. **Click**: "New Project"
4. **Select**: "Deploy from GitHub repo"
5. **Choose**: Your `enzura-backend` repository (or `backend` if you renamed it)
6. **Railway will auto-detect** Python

### 2.3 Configure Railway

1. **Click on your service** → Settings
2. **Set Root Directory**: `backend` (if deploying from monorepo)
3. **Set Start Command**: 
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

### 2.4 Add Environment Variables

Go to **Variables** tab, add:

```
OPENAI_API_KEY=your-actual-openai-key
OPENAI_MODEL=gpt-4o
SECRET_KEY=generate-this-with-python-secrets-token_urlsafe-32
ENVIRONMENT=production
```

### 2.5 Add Database

1. **Click**: "New" → "Database" → "PostgreSQL"
2. **Railway creates** database automatically
3. **Copy** the `DATABASE_URL` (it's auto-added to variables)
4. **Add** to environment variables:
   ```
   DATABASE_URL=postgresql://... (auto-filled by Railway)
   ```

### 2.6 Run Database Migration

1. **Click** on your PostgreSQL database
2. **Click** "Connect" → "Query"
3. **Copy** contents from `backend/migrations/add_performance_indexes.sql`
4. **Paste and run** in the query editor

### 2.7 Get Your Backend URL

1. **Click** on your web service
2. **Settings** → **Domains**
3. **Copy** the Railway-provided URL (e.g., `https://enzura-backend.railway.app`)
4. **Save this URL** - you'll need it for frontend!

### 2.8 Update CORS

1. **Go to Variables** tab
2. **Add**:
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app
   ```
   (We'll update this after frontend is deployed)

---

## 🌐 STEP 3: Deploy Frontend (Vercel)

### 3.1 Push Frontend to GitHub

```bash
# If not already a git repo (from project root):
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/enzura-frontend.git
git push -u origin main
```

**OR** if keeping monorepo:
- Just push the entire project
- We'll configure Vercel to build from root

### 3.2 Deploy on Vercel

1. **Go to**: https://vercel.com
2. **Sign up** with GitHub
3. **Click**: "Add New Project"
4. **Import** your GitHub repository
5. **Vercel auto-detects** React app ✅

### 3.3 Configure Vercel

**Build Settings** (usually auto-filled):
- **Framework Preset**: Create React App
- **Root Directory**: `./` (root)
- **Build Command**: `npm run build`
- **Output Directory**: `build`
- **Install Command**: `npm install`

### 3.4 Add Environment Variable

1. **Click**: "Environment Variables"
2. **Add**:
   ```
   Name: REACT_APP_API_URL
   Value: https://your-backend.railway.app/api
   ```
   (Use the Railway URL from Step 2.7)

3. **Select**: All environments (Production, Preview, Development)

### 3.5 Deploy

1. **Click**: "Deploy"
2. **Wait** 2-3 minutes
3. **Your app is live!** 🎉

### 3.6 Get Your Frontend URL

1. **Copy** your Vercel URL (e.g., `https://enzura-app.vercel.app`)
2. **Update backend CORS** (Step 3.7)

### 3.7 Update Backend CORS

1. **Go back to Railway**
2. **Variables** tab
3. **Update** `CORS_ORIGINS`:
   ```
   CORS_ORIGINS=https://enzura-app.vercel.app
   ```
4. **Railway auto-redeploys**

---

## ✅ STEP 4: Test Everything

### 4.1 Test Frontend
- Visit your Vercel URL
- Check browser console (F12) for errors
- Try logging in

### 4.2 Test Backend
- Visit: `https://your-backend.railway.app/`
- Should see: `{"message": "Enzura AI API is running!", ...}`
- Visit: `https://your-backend.railway.app/docs` (should be 404 in production ✅)

### 4.3 Test Connection
- Login from frontend
- Check Network tab (F12 → Network)
- Verify API calls go to Railway backend
- Check for CORS errors (should be none)

---

## 🔧 Common Issues & Fixes

### Issue: CORS Error
**Fix**: 
- Check `CORS_ORIGINS` in Railway includes your Vercel URL
- Make sure both URLs use `https://`

### Issue: API calls fail
**Fix**:
- Check `REACT_APP_API_URL` in Vercel includes `/api` at the end
- Verify backend is running (check Railway logs)

### Issue: Database connection fails
**Fix**:
- Verify `DATABASE_URL` in Railway is correct
- Check database is running (Railway dashboard)
- Ensure migration was run

### Issue: Environment variables not working
**Fix**:
- Rebuild frontend after adding env vars
- Check variable names (must start with `REACT_APP_` for frontend)
- Redeploy in Vercel

---

## 📋 Deployment Checklist

### Backend (Railway):
- [ ] Code pushed to GitHub
- [ ] Railway project created
- [ ] Environment variables set:
  - [ ] `OPENAI_API_KEY`
  - [ ] `OPENAI_MODEL`
  - [ ] `DATABASE_URL` (from Railway database)
  - [ ] `SECRET_KEY`
  - [ ] `ENVIRONMENT=production`
  - [ ] `CORS_ORIGINS` (update after frontend deploy)
- [ ] Database created
- [ ] Migration run
- [ ] Backend URL copied

### Frontend (Vercel):
- [ ] Code pushed to GitHub
- [ ] Vercel project created
- [ ] Environment variable set:
  - [ ] `REACT_APP_API_URL` (points to Railway backend + `/api`)
- [ ] Build successful
- [ ] Frontend URL copied

### Connection:
- [ ] Backend `CORS_ORIGINS` updated with frontend URL
- [ ] Test login works
- [ ] Test API calls work
- [ ] No console errors

---

## 🎯 Quick Reference

### Backend URL Format:
```
https://your-app.railway.app
```

### Frontend Environment Variable:
```
REACT_APP_API_URL=https://your-app.railway.app/api
```

### Backend CORS:
```
CORS_ORIGINS=https://your-app.vercel.app
```

### Generate Secret Key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 💡 Pro Tips

1. **Use Railway's free tier** for testing (usually enough for MVP)
2. **Vercel is free** for unlimited deployments
3. **Test locally first** before deploying
4. **Check logs** if something breaks (Railway and Vercel both have logs)
5. **Use custom domains** later (both platforms support it)

---

## 🆘 Need Help?

1. **Check logs**:
   - Railway: Dashboard → Your Service → Logs
   - Vercel: Dashboard → Your Project → Deployments → View Function Logs

2. **Test locally**:
   - Backend: `uvicorn app.main:app --reload`
   - Frontend: `npm start`
   - Verify everything works before deploying

3. **Common mistakes**:
   - Forgetting `/api` in `REACT_APP_API_URL`
   - Wrong CORS origins (must match exactly)
   - Database migration not run
   - Environment variables not set

---

**You're all set!** Follow these steps and your app will be live in ~30 minutes! 🚀

