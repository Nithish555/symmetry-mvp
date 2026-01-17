-- Symmetry MVP - PostgreSQL Schema (Enhanced with Sessions)
-- Run this in your Supabase SQL Editor

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================================
-- USERS TABLE
-- =========================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- SESSIONS TABLE (NEW - Groups related conversations)
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
-- CONVERSATIONS TABLE (Enhanced with session support)
-- =========================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    raw_messages JSONB NOT NULL,
    summary TEXT,
    topics TEXT[] DEFAULT '{}',
    entities TEXT[] DEFAULT '{}',
    embedding VECTOR(3072),
    message_count INTEGER DEFAULT 0,
    has_decisions BOOLEAN DEFAULT FALSE,
    has_facts BOOLEAN DEFAULT FALSE,
    session_status TEXT DEFAULT 'standalone',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- CHUNKS TABLE (For semantic search)
-- =========================================================================
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    chunk_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- SESSION SUGGESTIONS TABLE (For learning)
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
-- INDEXES
-- =========================================================================

-- User lookups
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Session lookups
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions(name);

-- Conversation lookups
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_source ON conversations(source);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_session_status ON conversations(session_status);

-- Chunk lookups
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_conversation_id ON chunks(conversation_id);

-- Vector similarity indexes (IVFFlat for 3072 dimensions)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_conversations_embedding ON conversations 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_sessions_embedding ON sessions 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- GIN indexes for array searches
CREATE INDEX IF NOT EXISTS idx_conversations_topics ON conversations USING GIN(topics);
CREATE INDEX IF NOT EXISTS idx_conversations_entities ON conversations USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_sessions_topics ON sessions USING GIN(topics);
CREATE INDEX IF NOT EXISTS idx_sessions_entities ON sessions USING GIN(entities);

-- =========================================================================
-- ROW LEVEL SECURITY
-- =========================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_suggestions ENABLE ROW LEVEL SECURITY;

-- =========================================================================
-- COMMENTS
-- =========================================================================
COMMENT ON TABLE users IS 'User accounts with API keys';
COMMENT ON TABLE sessions IS 'Session groups for related conversations across LLMs';
COMMENT ON TABLE conversations IS 'Raw conversation data with metadata (Memory Layer)';
COMMENT ON TABLE chunks IS 'Chunked text with embeddings for semantic search';
COMMENT ON TABLE session_suggestions IS 'Tracks AI session suggestions for learning';
