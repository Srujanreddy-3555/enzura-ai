# 🚨 Railway Deployment Troubleshooting

## Error: "Script start.sh not found" or "Railpack could not determine how to build"

This is the most common error when deploying to Railway. Here's how to fix it:

### ✅ Solution Steps:

1. **Set Root Directory** (CRITICAL):
   - Go to Railway → Your Service → **Settings** tab
   - Find **"Root Directory"** field
   - Type: `backend` (exactly this, no quotes, no slashes)
   - Click **Save**
   - Railway will automatically redeploy

2. **Verify Your Files**:
   - Make sure `Procfile` exists in `backend/` folder
   - Make sure `requirements.txt` exists in `backend/` folder
   - Make sure `runtime.txt` exists in `backend/` folder (optional but recommended)

3. **Check Procfile Content**:
   Your `backend/Procfile` should contain:
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. **Set Start Command Explicitly** (if still not working):
   - Go to Railway → Your Service → **Settings** tab
   - Find **"Start Command"** field
   - Type: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Click **Save**

5. **Wait for Redeploy**:
   - After saving, Railway will automatically redeploy
   - Wait 1-2 minutes for deployment to complete
   - Check the **Deployments** tab to see build progress

### 🔍 Why This Happens:

Railway's Railpack (build system) looks for Python files in the root directory. Since your app is in the `backend/` folder, it can't find:
- `main.py` (yours is at `backend/app/main.py`)
- `requirements.txt` (yours is at `backend/requirements.txt`)
- `Procfile` (yours is at `backend/Procfile`)

Setting the **Root Directory** to `backend` tells Railway where to look.

### 📋 Verification Checklist:

After setting root directory, verify:
- [ ] Root Directory is set to `backend`
- [ ] `Procfile` exists in `backend/Procfile`
- [ ] `requirements.txt` exists in `backend/requirements.txt`
- [ ] `runtime.txt` exists in `backend/runtime.txt` (optional)
- [ ] Start Command is set (or Procfile is detected)
- [ ] Deployment shows "Build successful" in logs

### 🎯 Quick Fix Command:

If you want to verify your files are correct, run this locally:

```bash
# Check Procfile
cat backend/Procfile

# Should output:
# web: uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Check requirements.txt exists
ls backend/requirements.txt

# Check runtime.txt
cat backend/runtime.txt
# Should output: python-3.11
```

### 📚 Reference:

According to [Railpack Python documentation](https://railpack.com/languages/python), Railway detects Python apps by:
- `main.py` in root directory
- `requirements.txt` file
- `pyproject.toml` file
- `Pipfile` file

Since your files are in `backend/`, you must set the Root Directory.

---

## Other Common Issues:

### Issue: Build succeeds but app crashes on start

**Check:**
1. Environment variables are set (especially `DATABASE_URL`)
2. Database is running and accessible
3. Start command is correct

### Issue: "Module not found" errors

**Check:**
1. All dependencies are in `requirements.txt`
2. `requirements.txt` is in the `backend/` folder
3. Root directory is set correctly

### Issue: Port binding errors

**Check:**
1. Start command uses `$PORT` (not a hardcoded port)
2. Start command is: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Issue: "ERROR: Could not find a version that satisfies the requirement python-magic-bin"

**Solution:**
1. `python-magic-bin` is Windows-only and doesn't work on Linux (Railway uses Linux)
2. **Remove** `python-magic-bin` from `requirements.txt`
3. **If you need file type detection**, use `python-magic` instead (requires system library `libmagic`)
4. **Commit and push** the updated `requirements.txt`
5. **Railway will automatically redeploy**

**Note:** If `python-magic-bin` is not used in your code, simply remove it. It was likely added by mistake.

---

**Still having issues?** Check Railway logs in the **Deployments** tab for specific error messages.

