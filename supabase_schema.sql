-- CodeLens Supabase Schema
-- Paste this into the Supabase SQL Editor and click "Run"

-- 1. Create a table to store users (synced from Clerk)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, -- Clerk User ID
    email TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 2. Create a table to track which user ingested which repository
CREATE TABLE IF NOT EXISTS user_repos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    repo_id TEXT NOT NULL, -- e.g., "owner/repo"
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(user_id, repo_id)
);

-- 3. Create a table to store the chat history
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    repo_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    citations JSONB, -- Store file:line references
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Note: We are using the Supabase REST API with the service/anon keys,
-- but for good measure, we can enable Row Level Security (RLS) if needed later.
-- For now, the FastAPI backend acts as a trusted server.
