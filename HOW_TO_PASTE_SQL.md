# 📋 How to Paste SQL in Railway CLI - Step by Step

## Visual Guide for Running Migration

### Step 1: Connect to Database
```bash
railway connect postgres
```

**What you'll see:**
```
Connecting to postgres...
psql (14.x)
Type "help" for help.

railway=#
```

The `railway=#` prompt means you're connected! ✅

---

### Step 2: Open Your SQL File

1. **Open** `backend/migrations/add_performance_indexes.sql` in:
   - Notepad
   - VS Code
   - Any text editor

2. **Select all** the content:
   - Press `Ctrl+A` (Windows) or `Cmd+A` (Mac)

3. **Copy** the content:
   - Press `Ctrl+C` (Windows) or `Cmd+C` (Mac)

---

### Step 3: Paste into Terminal

**Important**: You need to paste into the **same terminal window** where `railway connect postgres` is running!

1. **Click** on your terminal window (where you see `railway=#`)
2. **Right-click** in the terminal
3. **Select "Paste"** from the context menu
   - OR press `Ctrl+V` (Windows) or `Cmd+V` (Mac)

**What you'll see:**
```
railway=# -- Performance Indexes for Production
railway-# -- Run this migration to optimize queries...
railway-# 
railway-# CREATE INDEX IF NOT EXISTS idx_call_client_id ON call(client_id);
railway-# CREATE INDEX IF NOT EXISTS idx_call_user_id ON call(user_id);
...
```

**Note**: The `railway-#` prompt (with `#` instead of `=`) means psql is waiting for more SQL. This is normal!

---

### Step 4: Execute the SQL

1. **Press Enter** (after pasting)
2. **Wait** for execution to complete
3. You'll see output like:
   ```
   CREATE INDEX
   CREATE INDEX
   CREATE INDEX
   ...
   ANALYZE
   ANALYZE
   ```

4. **When you see** the prompt `railway=#` again (with `=` not `#`), it's done! ✅

---

### Step 5: Exit

1. **Type**: `\q`
2. **Press Enter**
3. You'll be back to your normal terminal prompt

---

## 🎯 Quick Summary

```
1. railway connect postgres          → Connects to database
2. Open SQL file in text editor      → backend/migrations/add_performance_indexes.sql
3. Copy all SQL (Ctrl+A, Ctrl+C)    → Select and copy
4. Paste in terminal (Right-click)  → Paste where railway=# is showing
5. Press Enter                       → Executes SQL
6. Wait for railway=# prompt        → Migration complete!
7. Type \q and Enter                 → Exit psql
```

---

## ❓ Troubleshooting

### "Nothing happens when I paste"
- Make sure you're pasting in the **same terminal** where `railway connect postgres` ran
- Try right-clicking and selecting "Paste" instead of Ctrl+V
- Some terminals need you to right-click to paste

### "I see railway-# but nothing happens"
- The `#` means psql is waiting for more SQL
- Just press **Enter** to execute what you pasted
- It will run all the SQL statements

### "I see errors"
- Check the error message
- Common issues:
  - Indexes already exist (safe to ignore - "IF NOT EXISTS" handles this)
  - Database connection lost (run `railway connect postgres` again)

### "How do I know it worked?"
- You'll see multiple "CREATE INDEX" messages
- You'll see "ANALYZE" messages at the end
- The prompt changes back to `railway=#` (with `=`)

---

## 💡 Pro Tip

If you want to see what indexes were created, before typing `\q`, you can run:
```sql
\di
```
This shows all indexes in the database.

Then type `\q` to exit.

---

**That's it!** Your migration is complete. ✅

