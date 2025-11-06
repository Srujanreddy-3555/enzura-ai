# 🔧 Fix: CORS Error - "No 'Access-Control-Allow-Origin' header"

## ❌ The Problem

You're seeing this error in browser console:
```
Access to fetch at 'https://enzura-ai-production.up.railway.app/api/auth/login' 
from origin 'https://enzura-ai.vercel.app' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

**This means**: Your Railway backend is blocking requests from your Vercel frontend!

---

## ✅ The Solution

Update the `CORS_ORIGINS` environment variable in Railway to include your Vercel URL.

### Step-by-Step Fix:

1. **Go to Railway** → Your main service (not Postgres)
2. **Click** **"Variables"** tab
3. **Find** `CORS_ORIGINS` variable
4. **Click** the **pencil icon** ✏️ to edit
5. **Set the value** to your Vercel URL:
   ```
   https://enzura-ai.vercel.app
   ```
   **⚠️ IMPORTANT**: 
   - Must include `https://`
   - Must match exactly (no trailing slash)
   - Case-sensitive

6. **Click** **"Save"** (or it auto-saves)

7. **Trigger Redeploy** (IMPORTANT!):
   - Go to **"Deployments"** tab
   - Click **"Redeploy"** button
   - Wait 1-2 minutes for deployment

8. **Test again** - Login should work now! ✅

---

## 🎯 Your Specific URLs

Based on your error:
- **Frontend**: `https://enzura-ai.vercel.app`
- **Backend**: `https://enzura-ai-production.up.railway.app`

**Set `CORS_ORIGINS` to:**
```
https://enzura-ai.vercel.app
```

---

## 📋 Quick Checklist

- [ ] Go to Railway → Main Service → Variables
- [ ] Find `CORS_ORIGINS` variable
- [ ] Set value to: `https://enzura-ai.vercel.app`
- [ ] Save the variable
- [ ] Go to Deployments tab
- [ ] Click "Redeploy"
- [ ] Wait for deployment (1-2 minutes)
- [ ] Try logging in again

---

## 🔍 Verify It's Fixed

After redeploying:

1. **Open** your login page
2. **Open** browser console (F12)
3. **Try logging in**
4. **Check console**:
   - ✅ No CORS errors
   - ✅ Login request succeeds (200 status)
   - ✅ You're redirected to dashboard

---

## ⚠️ Common Mistakes

### Wrong Format:
- ❌ `enzura-ai.vercel.app` (missing https://)
- ❌ `https://enzura-ai.vercel.app/` (trailing slash)
- ❌ `http://enzura-ai.vercel.app` (http instead of https)
- ❌ `https://www.enzura-ai.vercel.app` (www prefix if you don't use it)

### Correct Format:
- ✅ `https://enzura-ai.vercel.app` (exact match)

---

## 💡 Multiple Origins (If Needed)

If you have multiple frontend URLs (e.g., production + staging), separate them with commas:

```
https://enzura-ai.vercel.app,https://staging.enzura-ai.vercel.app
```

---

## 🆘 Still Not Working?

1. **Check** Railway logs after redeploy:
   - Should see backend starting successfully
   - No CORS-related errors

2. **Verify** `CORS_ORIGINS` value:
   - Must match your Vercel URL exactly
   - No extra spaces or characters

3. **Clear browser cache**:
   - Sometimes browsers cache CORS errors
   - Try incognito/private window

4. **Check** both URLs use `https://`:
   - Frontend: `https://enzura-ai.vercel.app`
   - Backend: `https://enzura-ai-production.up.railway.app`

---

**After updating CORS_ORIGINS and redeploying, your login should work!** ✅

