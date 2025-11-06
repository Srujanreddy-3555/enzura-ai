# 📊 Database Tables Guide

## ✅ Are Tables Created Automatically?

**YES!** Tables are created automatically when your backend starts.

### How It Works:

1. **On Startup**: When Railway deploys your backend, it runs the `startup_event()` function
2. **Table Creation**: The function calls `create_tables()` which creates all tables
3. **Check Logs**: You should see in Railway logs:
   ```
   Database tables created successfully!
   ```

### What Tables Are Created:

Your app creates **6 main tables**:

1. **`user`** - All users (Admin, Client, Rep)
2. **`client`** - Client companies
3. **`sales_rep`** - Sales representatives
4. **`call`** - Call records
5. **`transcript`** - Call transcripts
6. **`insights`** - AI-generated insights

---

## 📋 Table Details

### 1. `user` Table
**Stores**: All user accounts (Admin, Client users, Reps)

**Columns**:
- `id` - User ID (primary key)
- `email` - User email (unique)
- `password_hash` - Hashed password
- `name` - User's name
- `role` - ADMIN, CLIENT, or REP
- `client_id` - Which client this user belongs to (NULL for admin)
- `created_at` - When user was created
- `updated_at` - Last update time

**Example Data**:
```
id | email              | name        | role  | client_id
1  | admin@enzura.com   | Admin User  | ADMIN | NULL
2  | john@client.com     | John Doe    | CLIENT| 1
3  | rep@client.com      | Sales Rep   | REP   | 1
```

---

### 2. `client` Table
**Stores**: Client companies/organizations

**Columns**:
- `id` - Client ID (primary key)
- `name` - Client company name
- `s3_bucket_name` - AWS S3 bucket name
- `s3_region` - AWS region
- `aws_access_key` - AWS access key
- `aws_secret_key` - AWS secret key
- `processing_schedule` - How often to check S3 (realtime, hourly, daily)
- `timezone` - Client timezone
- `status` - active or inactive
- `created_at` - When client was created
- `updated_at` - Last update time

**Example Data**:
```
id | name          | s3_bucket_name | status
1  | Acme Corp     | acme-calls     | active
2  | Tech Solutions| tech-calls     | active
```

---

### 3. `sales_rep` Table
**Stores**: Sales representatives for each client

**Columns**:
- `id` - Sales rep ID (primary key)
- `client_id` - Which client this rep belongs to
- `name` - Sales rep name
- `email` - Sales rep email (optional)
- `phone` - Sales rep phone (optional)
- `created_at` - When rep was created

**Example Data**:
```
id | client_id | name        | email
1  | 1         | John Smith  | john@acme.com
2  | 1         | Jane Doe    | jane@acme.com
```

---

### 4. `call` Table
**Stores**: All call records

**Columns**:
- `id` - Call ID (primary key)
- `user_id` - Who uploaded the call
- `client_id` - Which client this call belongs to
- `sales_rep_id` - Which sales rep made the call
- `sales_rep_name` - Sales rep name (for quick access)
- `filename` - Original filename
- `s3_url` - S3 URL of the audio file
- `status` - PROCESSING, PROCESSED, or FAILED
- `language` - Detected language
- `translate_to_english` - Whether to translate
- `upload_date` - When call was uploaded
- `duration` - Call duration in seconds
- `score` - Quality score (0-100)
- `upload_method` - MANUAL or S3_AUTO

**Example Data**:
```
id | user_id | client_id | sales_rep_id | filename      | status     | score
1  | 2       | 1         | 1            | call1.mp3     | PROCESSED  | 85
2  | 2       | 1         | 2            | call2.wav     | PROCESSING | NULL
```

---

### 5. `transcript` Table
**Stores**: Call transcripts (text of what was said)

**Columns**:
- `id` - Transcript ID (primary key)
- `call_id` - Which call this transcript belongs to
- `text` - Full transcript text
- `language` - Detected language
- `created_at` - When transcript was created

**Example Data**:
```
id | call_id | text                    | language
1  | 1       | "Hello, how can I..."   | en
```

---

### 6. `insights` Table
**Stores**: AI-generated insights for each call

**Columns**:
- `id` - Insight ID (primary key)
- `call_id` - Which call this insight belongs to
- `summary` - Call summary
- `key_points` - Key discussion points
- `action_items` - Action items from call
- `sentiment` - positive, negative, or neutral
- `quality_score` - Quality score (0-100)
- `recommendations` - AI recommendations
- `created_at` - When insight was created

**Example Data**:
```
id | call_id | summary              | sentiment | quality_score
1  | 1       | "Customer interested"| positive  | 85
```

---

## 👀 Where to View Tables in Railway

### Method 1: Railway Database UI (Easiest)

1. **Go to** Railway → Your project
2. **Click** on your **Postgres** database service
3. **Click** **"Data"** tab
4. **Click** **"Tables"** (if available)
5. **You'll see** all your tables listed
6. **Click** on a table name to view data

**Note**: If "Tables" button isn't visible, use Method 2 or 3.

---

### Method 2: Railway CLI (Recommended)

1. **Install Railway CLI** (if not already):
   ```bash
   npm install -g @railway/cli
   ```

2. **Connect to database**:
   ```bash
   railway connect postgres
   ```

3. **List all tables**:
   ```sql
   \dt
   ```

4. **View table data**:
   ```sql
   SELECT * FROM "user";
   SELECT * FROM client;
   SELECT * FROM sales_rep;
   SELECT * FROM call;
   SELECT * FROM transcript;
   SELECT * FROM insights;
   ```

5. **Exit**:
   ```sql
   \q
   ```

---

### Method 3: Check Railway Logs

1. **Go to** Railway → Your main service
2. **Click** **"Deployments"** tab
3. **Click** on latest deployment
4. **Check logs** for:
   ```
   Database tables created successfully!
   ```
   This confirms tables were created.

---

## ✅ Verification Checklist

To verify tables are created:

- [ ] Check Railway logs show: `Database tables created successfully!`
- [ ] Can view tables in Railway Database UI (Method 1)
- [ ] Or use Railway CLI to list tables: `\dt` (Method 2)
- [ ] Can see your admin user in `user` table
- [ ] Can create clients and see them in `client` table
- [ ] Can create sales reps and see them in `sales_rep` table

---

## 🔍 Quick SQL Queries

If you can access the database, here are useful queries:

### Count records in each table:
```sql
SELECT 'user' as table_name, COUNT(*) as count FROM "user"
UNION ALL
SELECT 'client', COUNT(*) FROM client
UNION ALL
SELECT 'sales_rep', COUNT(*) FROM sales_rep
UNION ALL
SELECT 'call', COUNT(*) FROM call
UNION ALL
SELECT 'transcript', COUNT(*) FROM transcript
UNION ALL
SELECT 'insights', COUNT(*) FROM insights;
```

### View all users:
```sql
SELECT id, email, name, role, client_id, created_at FROM "user";
```

### View all clients:
```sql
SELECT id, name, status, created_at FROM client;
```

### View all calls with details:
```sql
SELECT c.id, c.filename, c.status, c.score, c.upload_date, 
       u.name as user_name, cl.name as client_name
FROM call c
LEFT JOIN "user" u ON c.user_id = u.id
LEFT JOIN client cl ON c.client_id = cl.id;
```

---

## 📝 Summary

**Tables are created automatically** when your backend starts! You can verify by:

1. ✅ Checking Railway logs for "Database tables created successfully!"
2. ✅ Using Railway Database UI to view tables
3. ✅ Using Railway CLI to connect and query tables
4. ✅ Creating data through your app and seeing it appear

**All your data** (clients, users, reps, calls, transcripts, insights) is stored in these tables and persists across deployments! ✅

