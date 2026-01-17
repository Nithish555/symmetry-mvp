-- Symmetry MVP - Database Migration Script
-- Run this in your Supabase SQL Editor to update existing tables

-- =========================================================================
-- ADD SESSIONS TABLE
-- =========================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    topics TEXT[] DEFAULT '{}',
    entities TEXT[] DEFAULT '{}',
    embedding VECTOR(3072),
    conversation_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- ADD SESSION SUGGESTIONS TABLE
-- =========================================================================
CREATE TABLE IF NOT EXISTS session_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    suggested_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    confidence FLOAT NOT NULL,
    accepted BOOLEAN,
    actual_session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- ADD NEW COLUMNS TO CONVERSATIONS TABLE
-- =========================================================================
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES sessions(id) ON DELETE SET NULL;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS topics TEXT[] DEFAULT '{}';

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS entities TEXT[] DEFAULT '{}';

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS embedding VECTOR(3072);

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS has_decisions BOOLEAN DEFAULT FALSE;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS has_facts BOOLEAN DEFAULT FALSE;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS session_status TEXT DEFAULT 'standalone';

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- =========================================================================
-- ADD NEW COLUMNS TO CHUNKS TABLE
-- =========================================================================
ALTER TABLE chunks 
ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 0;

-- =========================================================================
-- ADD NEW COLUMNS TO USERS TABLE
-- =========================================================================
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- =========================================================================
-- UPDATE EXISTING VECTOR DIMENSIONS (if needed)
-- =========================================================================
-- Note: If you already have data with 1536 dimensions, you may need to:
-- 1. Export existing embeddings
-- 2. Drop and recreate the column with 3072 dimensions
-- 3. Re-embed the data

-- Check current dimension:
-- SELECT embedding FROM chunks LIMIT 1;

-- If dimension is 1536, you need to re-embed or use 1536 model

-- =========================================================================
-- NEW INDEXES
-- =========================================================================
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions(name);

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_status ON conversations(session_status);

-- Vector indexes (IVFFlat for 3072 dimensions)
-- Note: These may fail if there's not enough data. Run after ingesting some conversations.
-- CREATE INDEX IF NOT EXISTS idx_conversations_embedding ON conversations 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- CREATE INDEX IF NOT EXISTS idx_sessions_embedding ON sessions 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- GIN indexes for array searches
CREATE INDEX IF NOT EXISTS idx_conversations_topics ON conversations USING GIN(topics);
CREATE INDEX IF NOT EXISTS idx_conversations_entities ON conversations USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_sessions_topics ON sessions USING GIN(topics);
CREATE INDEX IF NOT EXISTS idx_sessions_entities ON sessions USING GIN(entities);

-- =========================================================================
-- ROW LEVEL SECURITY
-- =========================================================================
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_suggestions ENABLE ROW LEVEL SECURITY;

-- =========================================================================
-- COMMENTS
-- =========================================================================
COMMENT ON TABLE sessions IS 'Session groups for related conversations across LLMs';
COMMENT ON TABLE session_suggestions IS 'Tracks AI session suggestions for learning';
COMMENT ON COLUMN conversations.session_status IS 'standalone=not linked, linked=in session, pending=awaiting confirmation';
