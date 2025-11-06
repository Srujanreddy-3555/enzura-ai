# 🔍 Debug: Login Failed - Step by Step

Let's troubleshoot why login is still failing even after creating the admin user.

---

## Step 1: Verify User Was Created

First, let's make sure the user actually exists in the database.

### Method A: Check via API

1. **Go to** your Railway backend: `https://your-app.railway.app/docs`
2. **Find** `/api/auth/me` endpoint (if available)
3. **Or** check Railway logs to see if user creation succeeded

### Method B: Check Database Directly

1. **Use Railway CLI**:
   ```bash
   railway connect postgres
   ```

2. **Check if user exists**:
   ```sql
   SELECT id, email, name, role FROM "user";
   ```

3. **You should see** your admin user listed
4. **If empty**, the user wasn't created - create it again

---

## Step 2: Check Browser Console

1. **Open** your login page
2. **Press F12** to open browser console
3. **Try logging in**
4. **Look for errors** in the Console tab:
   - Red error messages
   - Network errors
   - CORS errors

**Common errors to look for:**
- `Network Error` - Backend not reachable
- `CORS policy` - CORS misconfiguration
- `404 Not Found` - Wrong API URL
- `401 Unauthorized` - Wrong credentials

---

## Step 3: Check Network Tab

1. **Open** browser console (F12)
2. **Go to** "Network" tab
3. **Try logging in**
4. **Look for** the login request:
   - Should be: `POST /api/auth/login`
   - Check the **Request URL** - is it pointing to your Railway backend?
   - Check the **Status Code**:
     - `200` = Success (but frontend might be handling it wrong)
     - `401` = Wrong credentials
     - `404` = Wrong URL
     - `500` = Server error
     - `CORS error` = CORS issue

5. **Click** on the request to see:
   - **Request Payload** - What email/password is being sent?
   - **Response** - What error message is returned?

---

## Step 4: Verify Frontend API URL

1. **Go to** Vercel dashboard
2. **Click** on your project
3. **Go to** Settings → Environment Variables
4. **Check** `REACT_APP_API_URL`:
   - Should be: `https://your-app.railway.app/api`
   - **NOT**: `http://localhost:8000/api`
   - **NOT**: Missing `/api` at the end

5. **If wrong**, update it and **redeploy** Vercel

---

## Step 5: Test Login API Directly

Test if the login endpoint works by calling it directly:

### Option A: Using API Docs

1. **Go to**: `https://your-app.railway.app/docs`
2. **Find** `/api/auth/login` endpoint
3. **Click** "Try it out"
4. **Fill in**:
   - `username`: Your admin email
   - `password`: Your admin password
5. **Click** "Execute"
6. **Check response**:
   - ✅ Success = Login works, issue is in frontend
   - ❌ Error = Issue is in backend/credentials

### Option B: Using curl

```bash
curl -X POST "https://your-app.railway.app/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@enzura.com&password=your-password"
```

**If this works**, the backend is fine - issue is frontend connection.

---

## Step 6: Check Railway Logs

1. **Go to** Railway → Your main service
2. **Click** "Deployments" tab
3. **Click** on latest deployment
4. **Check logs** for:
   - Login attempts
   - Error messages
   - Database connection issues

**Look for:**
- `Database not available` - Database connection issue
- `Incorrect email or password` - Wrong credentials
- `401 Unauthorized` - Authentication failed

---

## Step 7: Verify Credentials

**Common mistakes:**
- ✅ Email: `admin@enzura.com` (exact match, case-sensitive)
- ❌ Email: `Admin@Enzura.com` (wrong case)
- ✅ Password: Exact password you used when registering
- ❌ Password: Different password or typos

**Try:**
1. Create a new test user with simple credentials:
   - Email: `test@test.com`
   - Password: `test123`
2. Try logging in with those credentials
3. If that works, the issue is with your admin credentials

---

## Step 8: Check CORS Configuration

1. **Go to** Railway → Your main service → Variables
2. **Check** `CORS_ORIGINS`:
   - Should include your Vercel URL: `https://your-app.vercel.app`
   - Must match exactly (including `https://`)
3. **If missing or wrong**, update it and redeploy

---

## 🎯 Quick Diagnostic Checklist

Run through these quickly:

- [ ] User exists in database? (Check with `SELECT * FROM "user";`)
- [ ] Browser console shows errors? (F12 → Console)
- [ ] Network tab shows login request? (F12 → Network)
- [ ] API URL correct in Vercel? (`https://your-app.railway.app/api`)
- [ ] Login works via API docs? (`/api/auth/login` in docs)
- [ ] Railway logs show login attempts?
- [ ] CORS_ORIGINS includes Vercel URL?
- [ ] Using exact email/password from registration?

---

## 💡 Most Common Issues

### Issue 1: Frontend Not Connected to Backend
**Symptoms**: Network error, 404, wrong URL
**Fix**: Check `REACT_APP_API_URL` in Vercel

### Issue 2: Wrong Credentials
**Symptoms**: 401 Unauthorized, "Incorrect email or password"
**Fix**: Double-check email/password, create new test user

### Issue 3: CORS Error
**Symptoms**: CORS policy error in console
**Fix**: Update `CORS_ORIGINS` in Railway

### Issue 4: User Not Created
**Symptoms**: Empty user table, 401 error
**Fix**: Create user again via API docs

### Issue 5: Database Connection Issue
**Symptoms**: "Database not available" in logs
**Fix**: Check `DATABASE_URL` in Railway Variables

---

## 🆘 Still Not Working?

**Share these details:**
1. What error message do you see? (exact text)
2. Browser console errors? (F12 → Console)
3. Network tab status code? (F12 → Network → Login request)
4. Does login work via API docs? (`/api/auth/login`)
5. Railway logs show any errors?

This will help pinpoint the exact issue!

