# Pre-Production Checklist

## 🔐 1. Environment Variables & Security

### Backend (`backend/.env`)
**Why:** Production requires secure, environment-specific configuration.

**Steps:**
1. Create `.env` file from `env.example`:
   ```bash
   cd backend
   cp env.example .env
   ```

2. Update with production values:
   - `OPENAI_API_KEY` - Your production OpenAI API key
   - `OPENAI_MODEL` - Keep as `gpt-4o` or your preferred model
   - `DATABASE_URL` - Production database connection string (Neon, AWS RDS, etc.)
   - `SECRET_KEY` - **CRITICAL**: Generate a strong random secret key (32+ characters)
     ```bash
     # Generate secret key (Python):
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```

3. **NEVER commit `.env` to git** - Verify it's in `.gitignore`

### Frontend (Environment Variables)
**Why:** Frontend needs to know where the production API is located.

**Steps:**
1. Create `.env` file in project root:
   ```bash
   # In project root
   REACT_APP_API_URL=https://your-api-domain.com/api
   ```

2. For production build, set this before building:
   ```bash
   set REACT_APP_API_URL=https://your-api-domain.com/api
   npm run build
   ```

---

## 🗄️ 2. Database Migration

### Run Performance Indexes
**Why:** Without indexes, queries will be slow with 200+ calls and 20+ clients.

**Steps:**
1. Connect to your production database
2. Run the migration:
   ```sql
   -- Copy contents from: backend/migrations/add_performance_indexes.sql
   -- Or run directly:
   psql $DATABASE_URL -f backend/migrations/add_performance_indexes.sql
   ```

3. Verify indexes were created:
   ```sql
   SELECT indexname FROM pg_indexes WHERE tablename = 'call';
   ```

**Expected:** You should see indexes like `idx_call_client_id`, `idx_call_user_id`, etc.

---

## 🔒 3. Security Hardening

### CORS Configuration
**Why:** Currently allows all origins (`allow_origins=["*"]`), which is insecure for production.

**Action Required:** Update `backend/app/main.py`:
```python
# Replace line 50:
allow_origins=["*"],  # ❌ Remove this

# With:
allow_origins=[
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com"
],  # ✅ Production domains only
```

### API Documentation
**Why:** Exposing `/docs` and `/redoc` in production can reveal API structure.

**Options:**
1. **Disable in production** (Recommended):
   ```python
   # In app/main.py, replace:
   docs_url="/docs",
   redoc_url="/redoc"
   
   # With:
   docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
   redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None,
   ```

2. **Or protect with authentication** (Alternative)

### Database Connection
**Why:** `echo=True` in database.py logs all SQL queries, which is a security risk.

**Action Required:** Update `backend/app/database.py`:
```python
# Replace line 24:
engine = create_engine(DATABASE_URL, echo=True)  # ❌ Remove echo=True

# With:
engine = create_engine(
    DATABASE_URL, 
    echo=os.getenv("ENVIRONMENT") != "production"  # ✅ Only in dev
)
```

---

## 🏗️ 4. Frontend Production Build

**Why:** Development builds are large and unoptimized. Production builds are minified and optimized.

**Steps:**
1. Set production API URL:
   ```bash
   set REACT_APP_API_URL=https://your-api-domain.com/api
   ```

2. Build for production:
   ```bash
   npm run build
   ```

3. Test the build locally:
   ```bash
   # Install serve globally (if not installed):
   npm install -g serve
   
   # Serve the build:
   serve -s build -l 3000
   ```

4. Verify:
   - All API calls work
   - No console errors
   - All routes work correctly

---

## 🧪 5. Testing Checklist

**Why:** Catch issues before users do.

### Backend Testing:
- [ ] Test login with all roles (Admin, Client, Rep)
- [ ] Test call upload and processing
- [ ] Test pagination with 200+ calls
- [ ] Test client management (create, update, delete)
- [ ] Test S3 monitoring (if enabled)
- [ ] Test error handling (invalid tokens, missing data)

### Frontend Testing:
- [ ] Test all routes and navigation
- [ ] Test authentication flow (login, logout)
- [ ] Test pagination in My Calls
- [ ] Test search and filters
- [ ] Test responsive design (mobile, tablet, desktop)
- [ ] Test error boundaries (intentionally break something)
- [ ] Test with slow network (throttle in DevTools)

---

## 📊 6. Performance Verification

**Why:** Ensure the app performs well under load.

**Checks:**
1. **Backend Response Times:**
   - Dashboard stats: < 500ms
   - Call list (paginated): < 300ms
   - Call details: < 200ms

2. **Frontend Load Times:**
   - Initial page load: < 3 seconds
   - Route navigation: < 500ms
   - API calls: < 1 second

3. **Database Queries:**
   - Verify indexes are being used:
     ```sql
     EXPLAIN ANALYZE SELECT * FROM call WHERE client_id = 1;
     ```
   - Should show "Index Scan" not "Seq Scan"

---

## 📝 7. Logging & Monitoring

**Why:** Need visibility into production issues.

### Backend Logging:
1. Set up proper logging:
   ```python
   import logging
   logging.basicConfig(
       level=logging.INFO if os.getenv("ENVIRONMENT") == "production" else logging.DEBUG
   )
   ```

2. Consider adding:
   - Error tracking (Sentry, Rollbar)
   - Performance monitoring (New Relic, Datadog)
   - Uptime monitoring (UptimeRobot, Pingdom)

### Frontend Error Tracking:
- ErrorBoundary is already implemented ✅
- Consider adding error reporting service

---

## 🚀 8. Deployment Configuration

### Backend Deployment:
1. **Server Requirements:**
   - Python 3.8+
   - PostgreSQL database
   - Environment variables set
   - Port 8000 (or configure reverse proxy)

2. **Start Command:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
   - `--workers 4` for production (adjust based on server CPU)

3. **Process Manager (Recommended):**
   - Use systemd (Linux), PM2, or supervisor
   - Auto-restart on crash
   - Log rotation

### Frontend Deployment:
1. **Static Hosting Options:**
   - Netlify
   - Vercel
   - AWS S3 + CloudFront
   - GitHub Pages

2. **Build Output:**
   - Deploy the `build/` folder
   - Configure redirects for React Router (all routes → index.html)

---

## 🔍 9. Pre-Launch Verification

**Final Checks:**
- [ ] All environment variables set correctly
- [ ] Database indexes created
- [ ] CORS configured for production domains
- [ ] API docs disabled or protected
- [ ] Database logging disabled (`echo=False`)
- [ ] Frontend built and tested
- [ ] All routes work correctly
- [ ] Authentication works
- [ ] Error handling works
- [ ] Mobile responsive
- [ ] No console errors
- [ ] `.env` files NOT in git
- [ ] Production secrets are secure

---

## 📋 10. Post-Deployment

**Immediate Checks:**
1. Monitor error logs for first 24 hours
2. Check API response times
3. Verify database performance
4. Test all critical user flows
5. Monitor server resources (CPU, memory)

---

## 🆘 Quick Reference

### Generate Secret Key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Test Database Connection:
```bash
psql $DATABASE_URL -c "SELECT 1;"
```

### Build Frontend:
```bash
set REACT_APP_API_URL=https://your-api.com/api
npm run build
```

### Run Backend (Production):
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## ⚠️ Critical Security Reminders

1. **NEVER** commit `.env` files
2. **ALWAYS** use strong `SECRET_KEY` (32+ random characters)
3. **RESTRICT** CORS to production domains only
4. **DISABLE** API docs in production (or protect with auth)
5. **DISABLE** SQL query logging in production
6. **USE** HTTPS in production (never HTTP)
7. **VALIDATE** all user inputs on backend
8. **LIMIT** API rate limiting (prevent abuse)

---

**Last Updated:** After optimization review
**Status:** Ready for production after completing this checklist

