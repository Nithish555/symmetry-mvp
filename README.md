# Symmetry

> **The Context OS for AI-Native Work**

Symmetry is a memory and knowledge layer that enables seamless conversation continuity across AI tools. Never lose context when switching between ChatGPT, Claude, Cursor, or any other AI assistant.

[![Version](https://img.shields.io/badge/version-1.0.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.11+-green)]()
[![License](https://img.shields.io/badge/license-MIT-purple)]()

---

## Table of Contents

1. [The Problem](#-the-problem)
2. [The Solution](#-the-solution)
3. [Quick Start](#-quick-start)
4. [Use Cases](#-use-cases)
5. [Architecture](#-architecture)
6. [Data Model](#-data-model)
7. [Key Techniques](#-key-techniques)
8. [API Reference](#-api-reference)
9. [Configuration](#-configuration)
10. [Why Not GraphRAG?](#-why-not-graphrag)
11. [Project Structure](#-project-structure)
12. [Roadmap](#-roadmap)

---

## 🎯 The Problem

When you work with AI assistants, your context is fragmented:

```
Monday (ChatGPT):    "I'm building an e-commerce site with React..."
Tuesday (Claude):    "I'm building an e-commerce site with React..." ← Repeating yourself!
Wednesday (Cursor):  "I'm building an e-commerce site with React..." ← Again!
```

**You shouldn't have to re-explain your project every time you switch tools.**

---

## 💡 The Solution

Symmetry captures, stores, and retrieves your AI conversation context:

```
Monday (ChatGPT):    "I'm building an e-commerce site with React..."
                            ↓ Symmetry captures this
Tuesday (Claude):    [Symmetry injects context] → Claude already knows your project!
Wednesday (Cursor):  [Symmetry injects context] → Cursor continues seamlessly!
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Cross-LLM Continuity** | Continue conversations across ChatGPT, Claude, Cursor, etc. |
| **Auto Session Detection** | Automatically groups related conversations (96%+ accuracy) |
| **Semantic Search** | Find relevant context using natural language queries |
| **Smart Recommendations** | Get suggestions for relevant past conversations |
| **Knowledge Extraction** | Automatically extracts decisions, facts, and entities |

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/symmetry-mvp.git
cd symmetry-mvp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your credentials
```

### 2. Database Setup

**PostgreSQL (Supabase):**
```bash
# Run in Supabase SQL Editor
scripts/setup_db.sql
```

**Neo4j (Optional):**
```bash
# Run in Neo4j Browser
scripts/setup_neo4j.cypher
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Register & Start Using

```bash
# Register
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'

# Save your API key from the response!
```

---

## 📋 Use Cases

### Overview

| Use Case | Endpoint | When to Use |
|----------|----------|-------------|
| Save a conversation | `POST /ingest` | After each AI conversation |
| Continue in new LLM | `POST /retrieve` (session mode) | Switching from ChatGPT to Claude |
| Find specific info | `POST /retrieve` (query mode) | "What database did I choose?" |
| Get all context | `POST /retrieve` (full mode) | Starting completely fresh |
| Find relevant context | `POST /recommend` | Before starting new conversation |
| Manage sessions | `POST /sessions` | Organize conversations manually |

---

### Use Case 1: Continue Project Across LLMs

**Scenario:** Started a project in ChatGPT, want to continue in Claude.

```
STEP 1: Save ChatGPT conversation
────────────────────────────────
POST /api/v1/ingest
{
  "source": "chatgpt",
  "messages": [
    {"role": "user", "content": "Building e-commerce with React..."},
    {"role": "assistant", "content": "Great! Use PostgreSQL..."}
  ]
}

Response:
{
  "conversation_id": "conv-123",
  "summary": "User building e-commerce with React, chose PostgreSQL"
}


STEP 2: Create/link to session
──────────────────────────────
POST /api/v1/sessions
{ "name": "E-commerce Project" }

POST /api/v1/sessions/{session_id}/conversations
{ "conversation_id": "conv-123" }


STEP 3: Get context for Claude
──────────────────────────────
POST /api/v1/retrieve
{ "mode": "session", "session_id": "..." }

Response includes ready-to-inject context_prompt:
┌──────────────────────────────────────────────────────────┐
│ [CONTEXT FROM PREVIOUS AI CONVERSATIONS]                 │
│                                                          │
│ ## Session: E-commerce Project                           │
│                                                          │
│ ### [chatgpt] - 2026-01-17                              │
│ USER: Building e-commerce with React...                  │
│ ASSISTANT: Great! Use PostgreSQL...                      │
│                                                          │
│ ## Key Decisions:                                        │
│ - Chose PostgreSQL for database                          │
│ - Using React + Node.js                                  │
│                                                          │
│ [END SYMMETRY CONTEXT]                                   │
└──────────────────────────────────────────────────────────┘

STEP 4: Paste into Claude and continue!
```

---

### Use Case 2: Auto-Session Detection

**Scenario:** Ingesting a new conversation that's related to an existing project.

```
POST /api/v1/ingest
{
  "source": "cursor",
  "messages": [{"role": "user", "content": "Help with React product catalog..."}],
  "auto_link_session": true
}

Symmetry automatically:
1. Generates embedding for new conversation
2. Searches existing sessions by similarity
3. Finds "E-commerce Project" with 96% match
4. Auto-links (confidence > 85%)

Response:
{
  "conversation_id": "conv-456",
  "session_suggestion": {
    "suggested_session": { "name": "E-commerce Project" },
    "confidence": 0.96,
    "auto_linked": true,
    "reason": "high_confidence"
  },
  "linked_session_id": "session-123"
}
```

**Confidence Rules:**
| Confidence | Action |
|------------|--------|
| > 85% | Auto-link (no user action needed) |
| 70-85% | Suggest to user for confirmation |
| < 70% | Keep standalone |

---

### Use Case 3: Query-Based Retrieval

**Scenario:** Find what you decided about a specific topic.

```
POST /api/v1/retrieve
{
  "mode": "query",
  "query": "what database did I choose for my project?"
}

Response:
{
  "summary": "You chose PostgreSQL because you need relational data 
              for products, orders, and users. Prisma was recommended 
              as the ORM.",
  "context_prompt": "[Ready-to-inject context...]",
  "chunks_found": 2
}
```

---

### Use Case 4: Get Recommendations

**Scenario:** Find relevant context before starting a new conversation.

```
POST /api/v1/recommend
{ "query": "implement Stripe payments" }

Response:
{
  "recommendations": [
    {
      "type": "session",
      "name": "E-commerce Project",
      "score": { "relevance": 0.89, "recency": 1.0, "final": 0.88 },
      "auto_select": true
    },
    {
      "type": "conversation", 
      "name": "Payment integration discussion",
      "score": { "final": 0.72 }
    }
  ],
  "auto_selected": { "name": "E-commerce Project" },
  "query_analysis": { "topics": ["payments", "Stripe"] }
}
```

---

### Use Case 5: Confirm Session Suggestions

**Scenario:** Symmetry suggests a session, but you want to create a new one.

```
# Option A: Accept suggestion
POST /api/v1/sessions/confirm-link
{
  "conversation_id": "conv-999",
  "action": "accept",
  "session_id": "session-456"
}

# Option B: Reject (keep standalone)
POST /api/v1/sessions/confirm-link
{
  "conversation_id": "conv-999",
  "action": "reject"
}

# Option C: Create new session
POST /api/v1/sessions/confirm-link
{
  "conversation_id": "conv-999",
  "action": "create_new",
  "new_session_name": "Client X Project"
}
```

---

### Use Case 6: Full Context Export

**Scenario:** Get ALL your context for a fresh start.

```
POST /api/v1/retrieve
{ "mode": "full", "limit": 20 }

Response:
{
  "summary": "Complete summary of all conversations...",
  "context_prompt": "
    [CONTEXT FROM ALL CONVERSATIONS]
    
    ### ChatGPT conversations...
    ### Claude conversations...
    ### Cursor conversations...
    
    ## All Decisions Made:
    - PostgreSQL for database
    - React + Node.js stack
    - Stripe for payments
    
    [END CONTEXT]
  ",
  "decisions": [...],
  "facts": [...],
  "entities": ["React", "PostgreSQL", "Stripe"]
}
```

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         SYMMETRY                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│   │ ChatGPT │  │ Claude  │  │ Cursor  │  │  Other  │           │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
│        └────────────┴────────────┴────────────┘                 │
│                          │                                       │
│                          ▼                                       │
│               ┌─────────────────────┐                           │
│               │    Symmetry API     │                           │
│               │     (FastAPI)       │                           │
│               └──────────┬──────────┘                           │
│                          │                                       │
│            ┌─────────────┴─────────────┐                        │
│            ▼                           ▼                        │
│   ┌─────────────────┐       ┌─────────────────┐                │
│   │  MEMORY LAYER   │       │ KNOWLEDGE LAYER │                │
│   │                 │       │                 │                │
│   │  PostgreSQL +   │       │     Neo4j       │                │
│   │  pgvector       │       │  (Optional)     │                │
│   │                 │       │                 │                │
│   │ • Conversations │       │ • Entities      │                │
│   │ • Chunks        │       │ • Relationships │                │
│   │ • Sessions      │       │ • Facts         │                │
│   │ • Embeddings    │       │ • Decisions     │                │
│   └─────────────────┘       └─────────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  /ingest     /retrieve    /recommend    /sessions    /users     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  SessionService      RecommendationService    EmbeddingService  │
│  ExtractionService   ChunkingService          SummarizationSvc  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│           PostgresDB                    Neo4jDB                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Ingest

```
POST /ingest
     │
     ▼
┌────────────────────┐
│ Generate Summary   │ ──→ LLM extracts summary, topics, entities
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Generate Embedding │ ──→ text-embedding-3-large (3072 dims)
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Session Detection  │ ──→ Search similar sessions, auto-link if >85%
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Store Conversation │ ──→ PostgreSQL with metadata
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Chunk & Embed      │ ──→ Split text, generate chunk embeddings
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Extract Knowledge  │ ──→ Neo4j: entities, relationships, facts
└────────────────────┘
     │
     ▼
Response: { conversation_id, session_suggestion, ... }
```

### Data Flow: Retrieve

```
POST /retrieve
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MODE SELECTION                              │
├─────────────────────────────────────────────────────────────────┤
│  "query"        → Semantic search chunks                        │
│  "session"      → Get all conversations in session              │
│  "conversation" → Get specific conversation                     │
│  "full"         → Get all user's context                        │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────┐
│ Fetch Knowledge    │ ──→ Neo4j: decisions, facts, entities
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Build Context      │ ──→ Generate context_prompt for LLM injection
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ Generate Summary   │ ──→ Human-readable summary
└────────────────────┘
     │
     ▼
Response: { summary, context_prompt, decisions, facts, ... }
```

---

## 📊 Data Model

### PostgreSQL Schema

```
USERS
├── id (UUID, PK)
├── email (TEXT, UNIQUE)
├── api_key (TEXT, UNIQUE)
└── created_at (TIMESTAMP)
        │
        │ 1:N
        ▼
SESSIONS
├── id (UUID, PK)
├── user_id (UUID, FK)
├── name (TEXT)
├── description (TEXT)
├── topics (TEXT[])
├── entities (TEXT[])
├── embedding (VECTOR 3072)
├── conversation_count (INT)
└── last_activity (TIMESTAMP)
        │
        │ 1:N
        ▼
CONVERSATIONS
├── id (UUID, PK)
├── user_id (UUID, FK)
├── session_id (UUID, FK, nullable)
├── source (TEXT: chatgpt, claude, cursor)
├── raw_messages (JSONB)
├── summary (TEXT)
├── topics (TEXT[])
├── entities (TEXT[])
├── embedding (VECTOR 3072)
├── session_status (TEXT: standalone, linked)
└── created_at (TIMESTAMP)
        │
        │ 1:N
        ▼
CHUNKS
├── id (UUID, PK)
├── conversation_id (UUID, FK)
├── user_id (UUID, FK)
├── content (TEXT)
├── embedding (VECTOR 3072)
└── chunk_index (INT)
```

### Neo4j Knowledge Graph

```
(User)───CHOSE───→(PostgreSQL)
   │                    │
   │                   FOR
   │                    │
 PREFERS                ▼
   │              (E-commerce)
   ▼                    │
(React)               USES
   │                    │
 USES                   ▼
   │               (Stripe)
   ▼
(Node.js)

Temporal Facts:
(User)──WORKS_ON──→(Project) [valid_from: 2026-01-17]
```

---

## 🧠 Key Techniques

### 1. Semantic Search

```
Query: "What database did I choose?"
          │
          ▼
    ┌───────────┐
    │ Embedding │  text-embedding-3-large
    │ [0.1,...] │  3072 dimensions
    └─────┬─────┘
          │
          ▼
┌─────────────────────────────────────────┐
│           pgvector Search               │
│                                         │
│  SELECT content,                        │
│         1 - (embedding <=> query) as s  │
│  FROM chunks                            │
│  WHERE s > 0.5                          │
│  ORDER BY s DESC                        │
│  LIMIT 5                                │
└─────────────────────────────────────────┘
          │
          ▼
Results:
├── "I will use PostgreSQL..." (0.89)
└── "PostgreSQL is solid..."   (0.85)
```

### 2. Session Auto-Detection

```
New conversation embedding
          │
          ▼
Search existing sessions
          │
          ▼
┌─────────────────────────────────┐
│ Session              │ Score   │
├──────────────────────┼─────────┤
│ E-commerce Project   │ 0.96 ✓  │
│ React Learning       │ 0.68    │
│ Personal Blog        │ 0.32    │
└──────────────────────┴─────────┘
          │
          ▼
Apply confidence rules:
• 0.96 > 0.85 threshold ✓
• 0.96 - 0.68 = 0.28 > 0.15 margin ✓
• Decision: AUTO-LINK
```

### 3. Recommendation Scoring

```
Final Score = (Relevance × 0.60) + (Recency × 0.25) + (Quality × 0.15)

┌─────────────────────────────────────────────────────────────────┐
│ RELEVANCE (60%)                                                 │
│ • Semantic similarity to query                                  │
│ • Topic overlap bonus (+0.1 per match)                         │
├─────────────────────────────────────────────────────────────────┤
│ RECENCY (25%)                                                   │
│ • < 24 hours: 1.0                                              │
│ • 1-30 days: Linear decay                                      │
│ • > 30 days: 0.0                                               │
├─────────────────────────────────────────────────────────────────┤
│ QUALITY (15%)                                                   │
│ • Has summary: +0.3                                            │
│ • Has topics: +0.2                                             │
│ • Has entities: +0.2                                           │
│ • Messages ≥ 10: +0.3                                          │
└─────────────────────────────────────────────────────────────────┘

Auto-Selection: Score > 0.85 AND margin > 0.20
```

### 4. Context Prompt Structure

```
[CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]

## Session: E-commerce Project
Description: Building online store with React, Node.js, PostgreSQL

## Conversation History (chronological):

### [chatgpt] - 2026-01-17
**USER**: I want to build an e-commerce site...
**ASSISTANT**: Great choice! React is excellent...

### [claude] - 2026-01-17
**USER**: Help with product catalog...
**ASSISTANT**: For a product catalog...

## Key Decisions Made:
- Chose PostgreSQL (Reason: relational data needs)
- Using Prisma as ORM
- Stripe for payments

## Current Facts:
- Project USES React
- Project USES Node.js

## Instructions:
- Use this context to maintain continuity
- Don't ask questions already answered
- Reference past decisions when relevant

[END SYMMETRY CONTEXT]
```

---

## 📖 API Reference

### Authentication

All endpoints require Bearer token:
```bash
Authorization: Bearer sk_your_api_key
```

### Endpoints

#### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/users/register` | Register new user |

```bash
# Register
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# Response
{
  "user_id": "...",
  "api_key": "sk_...",
  "message": "Store your API key securely"
}
```

#### Ingest

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ingest` | Store a conversation |

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer sk_..." \
  -H "Content-Type: application/json" \
  -d '{
    "source": "chatgpt",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ],
    "auto_link_session": true
  }'
```

#### Retrieve

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/retrieve` | Get context |

```bash
# Query mode
curl -X POST http://localhost:8000/api/v1/retrieve \
  -H "Authorization: Bearer sk_..." \
  -d '{"mode": "query", "query": "what database?"}'

# Session mode
curl -X POST http://localhost:8000/api/v1/retrieve \
  -d '{"mode": "session", "session_id": "..."}'

# Full mode
curl -X POST http://localhost:8000/api/v1/retrieve \
  -d '{"mode": "full", "limit": 10}'
```

#### Recommend

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/recommend` | Get recommendations |

```bash
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Authorization: Bearer sk_..." \
  -d '{"query": "continue e-commerce project"}'
```

#### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sessions` | List sessions |
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions/{id}` | Get session |
| PATCH | `/api/v1/sessions/{id}` | Update session |
| DELETE | `/api/v1/sessions/{id}` | Delete session |
| POST | `/api/v1/sessions/{id}/conversations` | Link conversation |
| POST | `/api/v1/sessions/confirm-link` | Confirm suggestion |

---

## ⚙️ Configuration

### Environment Variables

```env
# Database (Supabase)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_KEY=...

# Neo4j (Optional)
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# LLM Provider
LLM_PROVIDER=azure_openai  # or "openai"

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Embeddings
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://...
AZURE_OPENAI_EMBEDDING_API_KEY=...
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Settings
CHUNK_SIZE=500
CHUNK_OVERLAP=50
SIMILARITY_THRESHOLD=0.5
```

---

## 🤔 Why Not GraphRAG?

| Aspect | Symmetry | GraphRAG |
|--------|----------|----------|
| **Use Case** | Conversation continuity | Global knowledge synthesis |
| **Query Type** | "Continue my project" | "Patterns across all docs" |
| **Latency** | 1-2 seconds | 5-10 seconds |
| **Complexity** | Moderate | High |
| **Cost** | Lower | Higher |

**Symmetry's session-based approach provides similar benefits to GraphRAG's communities, optimized for real-time context injection.**

---

## 📁 Project Structure

```
symmetry-mvp/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration
│   ├── api/
│   │   ├── dependencies.py     # Auth, DB injection
│   │   └── routes/
│   │       ├── users.py
│   │       ├── ingest.py
│   │       ├── retrieve.py
│   │       ├── recommend.py
│   │       ├── sessions.py
│   │       └── conversations.py
│   ├── db/
│   │   ├── postgres.py         # PostgreSQL client
│   │   └── neo4j.py            # Neo4j client
│   ├── services/
│   │   ├── session.py          # Session detection
│   │   ├── recommendation.py   # Scoring algorithm
│   │   ├── embedding.py        # Vector embeddings
│   │   ├── extraction.py       # Knowledge extraction
│   │   ├── chunking.py         # Text chunking
│   │   └── summarization.py    # Summaries
│   └── models/
│       ├── requests.py         # Request schemas
│       └── responses.py        # Response schemas
├── scripts/
│   ├── setup_db.sql            # PostgreSQL schema
│   └── setup_neo4j.cypher      # Neo4j schema
├── requirements.txt
├── env.example
└── README.md
```

---

## 🔒 Security

- **API Key Authentication** - All requests require valid API key
- **User Isolation** - Users can only access their own data
- **Row Level Security** - Enabled on all PostgreSQL tables
- **No PII in Logs** - Sensitive data is not logged

---

## 📈 Performance

| Operation | Latency |
|-----------|---------|
| Ingest | 3-8 sec |
| Retrieve (query) | 1-2 sec |
| Retrieve (session) | 1-3 sec |
| Recommend | 2-4 sec |

---

## 🛣️ Roadmap

- [ ] Browser extension for automatic capture
- [ ] CLI tool for developers
- [ ] Webhook support for real-time sync
- [ ] Team/organization support
- [ ] Conflict detection
- [ ] Export/import functionality

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Symmetry</strong> — Never lose context again.
</p>
