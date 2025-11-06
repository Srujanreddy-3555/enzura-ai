-- Performance Indexes for Production
-- Run this migration to optimize queries with 200+ calls and 20+ clients

-- Indexes for Call table (most frequently queried)
CREATE INDEX IF NOT EXISTS idx_call_client_id ON call(client_id);
CREATE INDEX IF NOT EXISTS idx_call_user_id ON call(user_id);
CREATE INDEX IF NOT EXISTS idx_call_status ON call(status);
CREATE INDEX IF NOT EXISTS idx_call_upload_date ON call(upload_date DESC);
CREATE INDEX IF NOT EXISTS idx_call_sales_rep_id ON call(sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_call_client_status ON call(client_id, status);
CREATE INDEX IF NOT EXISTS idx_call_user_client ON call(user_id, client_id);

-- Indexes for Insights table
CREATE INDEX IF NOT EXISTS idx_insights_call_id ON insights(call_id);

-- Indexes for User table
CREATE INDEX IF NOT EXISTS idx_user_client_id ON "user"(client_id);
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);

-- Indexes for Client table
CREATE INDEX IF NOT EXISTS idx_client_name ON client(name);
CREATE INDEX IF NOT EXISTS idx_client_status ON client(status);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_call_client_upload_date ON call(client_id, upload_date DESC);
CREATE INDEX IF NOT EXISTS idx_call_user_upload_date ON call(user_id, upload_date DESC);

-- Analyze tables after creating indexes
ANALYZE call;
ANALYZE insights;
ANALYZE "user";
ANALYZE client;

