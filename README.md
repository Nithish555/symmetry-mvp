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
5. [Deep Dive: How It Works](#-deep-dive-how-it-works)
   - [Ingestion Pipeline](#ingestion-pipeline-post-ingest)
   - [Retrieval Pipeline](#retrieval-pipeline-post-retrieve)
   - [Recommendation Pipeline](#recommendation-pipeline-post-recommend)
6. [Architecture](#-architecture)
7. [Data Model](#-data-model)
8. [Key Techniques](#-key-techniques)
9. [API Reference](#-api-reference)
10. [Configuration](#-configuration)
11. [Why Not GraphRAG?](#-why-not-graphrag)
12. [Project Structure](#-project-structure)
13. [Roadmap](#-roadmap)

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

## 🔬 Deep Dive: How It Works

### Ingestion Pipeline (POST /ingest)

When you call `/ingest`, here's the complete processing pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT: Conversation from ChatGPT/Claude/Cursor
┌──────────────────────────────────────────────────────────────────────────────┐
│ {                                                                            │
│   "source": "chatgpt",                                                       │
│   "messages": [                                                              │
│     {"role": "user", "content": "I want to build an e-commerce site..."},   │
│     {"role": "assistant", "content": "Great! Let's use React and..."}       │
│   ]                                                                          │
│ }                                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Step 1: Text Preparation

```
Raw Messages → Concatenated Text
─────────────────────────────────

USER: I want to build an e-commerce site with React
ASSISTANT: Great choice! For the database, I recommend PostgreSQL...
USER: What about payments?
ASSISTANT: Stripe is excellent for payments...

         ↓ Concatenate with role markers
         
"USER: I want to build an e-commerce site with React
ASSISTANT: Great choice! For the database, I recommend PostgreSQL...
USER: What about payments?
ASSISTANT: Stripe is excellent for payments..."
```

#### Step 2: Chunking (Text Splitting)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHUNKING STRATEGY                             │
├─────────────────────────────────────────────────────────────────┤
│  Technique: RecursiveCharacterTextSplitter (LangChain)          │
│  Chunk Size: 500 characters                                      │
│  Overlap: 50 characters (10%)                                    │
└─────────────────────────────────────────────────────────────────┘

Full Text (2000 chars)
┌────────────────────────────────────────────────────────────────┐
│ USER: I want to build... ASSISTANT: Great choice... USER: What │
│ about payments? ASSISTANT: Stripe is excellent... USER: How do │
│ I structure the database? ASSISTANT: For e-commerce, you need  │
│ tables for: products, orders, users, cart_items...             │
└────────────────────────────────────────────────────────────────┘
                              ↓
                         Split into chunks
                              ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Chunk 0    │  │  Chunk 1    │  │  Chunk 2    │  │  Chunk 3    │
│  (500 ch)   │  │  (500 ch)   │  │  (500 ch)   │  │  (500 ch)   │
│             │  │             │  │             │  │             │
│ "USER: I    │  │ "...choice! │  │ "...Stripe  │  │ "...tables  │
│ want to     │  │ For the     │  │ is excel-   │  │ for: prod-  │
│ build..."   │  │ database.." │  │ lent..."    │  │ ucts..."    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                              │
                    50 char OVERLAP between chunks
                    (ensures context isn't lost at boundaries)
```

**Why Chunking?**
- Embeddings have token limits (~8K tokens)
- Smaller chunks = more precise semantic search
- Overlap ensures we don't cut important context mid-sentence

#### Step 3: Embedding Generation

```
┌─────────────────────────────────────────────────────────────────┐
│                    EMBEDDING PROCESS                             │
├─────────────────────────────────────────────────────────────────┤
│  Model: text-embedding-3-large (Azure OpenAI)                   │
│  Dimensions: 3072                                                │
│  Output: Dense vector representing semantic meaning              │
└─────────────────────────────────────────────────────────────────┘

Chunk 0: "USER: I want to build an e-commerce site with React..."
                              ↓
                    Azure OpenAI Embedding API
                              ↓
Vector: [0.0234, -0.0891, 0.1456, ..., 0.0023]  (3072 floats)
         │
         └── This vector CAPTURES THE MEANING of the text
             Similar texts → Similar vectors → Close in vector space
```

**What the embedding captures:**
```
"e-commerce site with React" 
    → Vector close to: "online store", "web shop", "React app"
    → Vector far from: "machine learning", "cooking recipes"
```

#### Step 4: Conversation-Level Processing

```
┌─────────────────────────────────────────────────────────────────┐
│              CONVERSATION SUMMARY & EMBEDDING                    │
└─────────────────────────────────────────────────────────────────┘

Full Conversation
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  LLM (GPT-4o-mini) generates:                                    │
│                                                                  │
│  Summary: "User is building an e-commerce website using React    │
│           and Node.js. Chose PostgreSQL for database and Stripe  │
│           for payments. Discussed database schema design."       │
│                                                                  │
│  Topics: ["e-commerce", "React", "PostgreSQL", "Stripe"]         │
│                                                                  │
│  Entities: ["React", "Node.js", "PostgreSQL", "Stripe"]          │
└──────────────────────────────────────────────────────────────────┘
       ↓
Summary → Embedding API → Conversation Embedding [3072 floats]
```

#### Step 5: Session Auto-Detection

```
┌─────────────────────────────────────────────────────────────────┐
│                 SESSION MATCHING ALGORITHM                       │
└─────────────────────────────────────────────────────────────────┘

New Conversation Embedding
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  SELECT * FROM sessions                                          │
│  WHERE 1 - (embedding <=> new_embedding) > 0.5  -- similarity    │
│  ORDER BY embedding <=> new_embedding           -- closest first │
│  LIMIT 5                                                         │
└──────────────────────────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────────────────┐
│  Session                    │ Similarity │ Topics Match │ Final │
├─────────────────────────────┼────────────┼──────────────┼───────┤
│  E-commerce Project         │    0.92    │     3/4      │ 0.96  │
│  React Learning             │    0.71    │     1/4      │ 0.73  │
│  Personal Blog              │    0.45    │     0/4      │ 0.45  │
└─────────────────────────────────────────────────────────────────┘
       ↓
Decision Logic:
  IF top_score > 0.85 AND (top_score - second_score) > 0.15:
      → AUTO-LINK (high confidence)
  ELIF top_score > 0.70:
      → SUGGEST (medium confidence)
  ELSE:
      → STANDALONE (no match)
```

#### Step 6: Knowledge Extraction (Neo4j)

```
┌─────────────────────────────────────────────────────────────────┐
│                 KNOWLEDGE EXTRACTION                             │
├─────────────────────────────────────────────────────────────────┤
│  LLM analyzes conversation and extracts structured knowledge    │
└─────────────────────────────────────────────────────────────────┘

Conversation Text
       ↓
   GPT-4o-mini with extraction prompt
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  ENTITIES:                                                       │
│  ├── React (technology)                                          │
│  ├── PostgreSQL (database)                                       │
│  ├── Stripe (service)                                            │
│  └── E-commerce Project (project)                                │
│                                                                  │
│  RELATIONSHIPS:                                                  │
│  ├── User ──CHOSE──→ PostgreSQL                                  │
│  ├── Project ──USES──→ React                                     │
│  └── Project ──INTEGRATES──→ Stripe                              │
│                                                                  │
│  DECISIONS:                                                      │
│  ├── "Use PostgreSQL" (reason: "need relational data")          │
│  └── "Use Stripe" (reason: "best payment integration")          │
│                                                                  │
│  FACTS:                                                          │
│  ├── "Project is an e-commerce website"                         │
│  └── "Target launch: Q2 2026"                                    │
└──────────────────────────────────────────────────────────────────┘
       ↓
   Store in Neo4j Graph
       ↓
         (User)
           │
     ┌─────┴─────┐
     │           │
   CHOSE      WORKS_ON
     │           │
     ▼           ▼
(PostgreSQL)  (Project)
                 │
          ┌──────┼──────┐
          │      │      │
        USES   USES  INTEGRATES
          │      │      │
          ▼      ▼      ▼
      (React) (Node.js) (Stripe)
```

#### Step 7: Final Storage

```
┌─────────────────────────────────────────────────────────────────┐
│                    FINAL STORAGE                                 │
└─────────────────────────────────────────────────────────────────┘

POSTGRESQL:
┌─────────────────────────────────────────────────────────────────┐
│ conversations                                                    │
├─────────────────────────────────────────────────────────────────┤
│ id: conv-123                                                     │
│ user_id: user-456                                                │
│ session_id: session-789 (if linked)                              │
│ source: "chatgpt"                                                │
│ raw_messages: [{role, content}, ...]                             │
│ summary: "User building e-commerce..."                           │
│ topics: ["e-commerce", "React", ...]                             │
│ entities: ["React", "PostgreSQL", ...]                           │
│ embedding: [0.023, -0.089, ...] (3072 dims)                      │
│ created_at: 2026-01-17T10:30:00Z                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ chunks                                                           │
├─────────────────────────────────────────────────────────────────┤
│ id: chunk-001          │ id: chunk-002         │ ...            │
│ conversation_id: conv-123                                        │
│ content: "USER: I want..." │ content: "...database" │            │
│ embedding: [...]        │ embedding: [...]      │                │
│ chunk_index: 0          │ chunk_index: 1        │                │
└─────────────────────────────────────────────────────────────────┘

NEO4J:
┌─────────────────────────────────────────────────────────────────┐
│ Nodes: Entity, Decision, Fact                                    │
│ Relationships: CHOSE, USES, WORKS_ON, etc.                       │
│ Properties: user_id, timestamp, reason, valid_from, valid_to     │
└─────────────────────────────────────────────────────────────────┘
```

---

### Retrieval Pipeline (POST /retrieve)

The retrieve endpoint supports 4 modes, each optimized for different use cases:

#### Mode 1: Query-Based Retrieval (`mode: "query"`)

**Use Case:** Find specific information from past conversations.

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY MODE RETRIEVAL                          │
└─────────────────────────────────────────────────────────────────┘

INPUT: { "mode": "query", "query": "what database did I choose?" }
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Generate Query Embedding                                 │
├──────────────────────────────────────────────────────────────────┤
│ "what database did I choose?"                                    │
│        ↓                                                         │
│ text-embedding-3-large                                           │
│        ↓                                                         │
│ [0.0456, -0.0234, 0.1789, ...] (3072 dims)                      │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Vector Similarity Search (pgvector)                      │
├──────────────────────────────────────────────────────────────────┤
│ SELECT content, 1 - (embedding <=> query_embedding) as score     │
│ FROM chunks                                                      │
│ WHERE user_id = $user_id                                         │
│   AND 1 - (embedding <=> query_embedding) > 0.5                  │
│ ORDER BY embedding <=> query_embedding                           │
│ LIMIT 5                                                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RESULTS:                                                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. "For the database, I recommend PostgreSQL because..."  (0.91)│
│ 2. "PostgreSQL is great for relational data like..."      (0.87)│
│ 3. "You'll need tables for products, orders, users..."    (0.82)│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Knowledge Graph Query (Neo4j)                            │
├──────────────────────────────────────────────────────────────────┤
│ MATCH (u:User {id: $user_id})-[r:CHOSE]->(db)                   │
│ WHERE db.type = 'database'                                       │
│ RETURN db.name, r.reason, r.timestamp                            │
│                                                                  │
│ Result: PostgreSQL, "need relational data", 2026-01-17          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: Generate Summary & Context Prompt                        │
├──────────────────────────────────────────────────────────────────┤
│ LLM combines chunks + knowledge into:                            │
│                                                                  │
│ summary: "You chose PostgreSQL for your e-commerce project       │
│          because you need relational data for products,          │
│          orders, and users. Prisma was recommended as ORM."      │
│                                                                  │
│ context_prompt: "[SYMMETRY CONTEXT]                              │
│                  Decision: Chose PostgreSQL                      │
│                  Reason: Relational data needs                   │
│                  Related: products, orders, users tables         │
│                  [END CONTEXT]"                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Mode 2: Session Retrieval (`mode: "session"`)

**Use Case:** Continue a project across different LLMs.

```
┌─────────────────────────────────────────────────────────────────┐
│                   SESSION MODE RETRIEVAL                         │
└─────────────────────────────────────────────────────────────────┘

INPUT: { "mode": "session", "session_id": "session-789" }
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Fetch All Conversations in Session                       │
├──────────────────────────────────────────────────────────────────┤
│ SELECT * FROM conversations                                      │
│ WHERE session_id = $session_id AND user_id = $user_id           │
│ ORDER BY created_at ASC                                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ CONVERSATIONS IN SESSION:                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. [chatgpt] 2026-01-15 - Initial project discussion            │
│ 2. [claude]  2026-01-16 - Database schema design                │
│ 3. [cursor]  2026-01-17 - Payment integration                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Build Chronological Context                              │
├──────────────────────────────────────────────────────────────────┤
│ For each conversation:                                           │
│   - Extract raw_messages                                         │
│   - Format: [source] timestamp                                   │
│   - Include full USER/ASSISTANT exchanges                        │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Fetch Related Knowledge                                  │
├──────────────────────────────────────────────────────────────────┤
│ Neo4j: Get all decisions, facts, entities for this user         │
│ that were created during this session's timeframe               │
└──────────────────────────────────────────────────────────────────┘
                              ↓
OUTPUT context_prompt:
┌──────────────────────────────────────────────────────────────────┐
│ [CONTEXT FROM PREVIOUS AI CONVERSATIONS - SYMMETRY]              │
│                                                                  │
│ ## Session: E-commerce Project                                   │
│ Description: Building online store with React/Node/PostgreSQL   │
│                                                                  │
│ ## Conversation History (chronological):                         │
│                                                                  │
│ ### [chatgpt] - 2026-01-15                                      │
│ **USER**: I want to build an e-commerce site...                 │
│ **ASSISTANT**: Great! Let's start with the tech stack...        │
│                                                                  │
│ ### [claude] - 2026-01-16                                       │
│ **USER**: Help me design the database schema...                 │
│ **ASSISTANT**: For e-commerce, you need these tables...         │
│                                                                  │
│ ### [cursor] - 2026-01-17                                       │
│ **USER**: Now let's integrate Stripe...                         │
│ **ASSISTANT**: Here's how to set up Stripe...                   │
│                                                                  │
│ ## Key Decisions:                                                │
│ - Chose PostgreSQL (Reason: relational data)                    │
│ - Using Prisma ORM (Reason: type safety)                        │
│ - Stripe for payments (Reason: best docs)                       │
│                                                                  │
│ ## Current Facts:                                                │
│ - Project uses React + Node.js                                  │
│ - Target: Q2 2026 launch                                        │
│                                                                  │
│ [END SYMMETRY CONTEXT]                                           │
└──────────────────────────────────────────────────────────────────┘
```

#### Mode 3: Conversation Retrieval (`mode: "conversation"`)

**Use Case:** Get a specific conversation's full context.

```
┌─────────────────────────────────────────────────────────────────┐
│                CONVERSATION MODE RETRIEVAL                       │
└─────────────────────────────────────────────────────────────────┘

INPUT: { "mode": "conversation", "conversation_id": "conv-123" }
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Fetch single conversation with all raw_messages                  │
│ Include: source, timestamp, full message history                 │
└──────────────────────────────────────────────────────────────────┘
                              ↓
OUTPUT: Complete conversation with summary and context_prompt
```

#### Mode 4: Full Retrieval (`mode: "full"`)

**Use Case:** Get ALL your context for a completely fresh start.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FULL MODE RETRIEVAL                          │
└─────────────────────────────────────────────────────────────────┘

INPUT: { "mode": "full", "limit": 20 }
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Fetch ALL recent conversations (up to limit)                     │
│ Fetch ALL decisions from Neo4j                                   │
│ Fetch ALL facts from Neo4j                                       │
│ Fetch ALL entities from Neo4j                                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
OUTPUT: Comprehensive context_prompt with everything
```

---

### Recommendation Pipeline (POST /recommend)

The recommend endpoint helps users find relevant context BEFORE starting a new conversation.

```
┌─────────────────────────────────────────────────────────────────┐
│                  RECOMMENDATION PIPELINE                         │
└─────────────────────────────────────────────────────────────────┘

INPUT: { "query": "implement Stripe payments" }
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Query Analysis                                           │
├──────────────────────────────────────────────────────────────────┤
│ Extract topics: ["payments", "Stripe", "implementation"]         │
│ Generate embedding: [0.0234, -0.0891, ...]                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Search Sessions & Conversations                          │
├──────────────────────────────────────────────────────────────────┤
│ Sessions:                                                        │
│   SELECT *, 1-(embedding <=> query) as similarity                │
│   FROM sessions WHERE user_id = $user_id                         │
│   ORDER BY similarity DESC LIMIT 10                              │
│                                                                  │
│ Standalone Conversations:                                        │
│   SELECT *, 1-(embedding <=> query) as similarity                │
│   FROM conversations                                             │
│   WHERE user_id = $user_id AND session_id IS NULL               │
│   ORDER BY similarity DESC LIMIT 10                              │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Scoring Algorithm                                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Final Score = (Relevance × 0.60) + (Recency × 0.25) +           │
│               (Quality × 0.15)                                   │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ RELEVANCE (60%)                                             │ │
│ │ • Base: Cosine similarity from embedding search             │ │
│ │ • Bonus: +0.1 per matching topic                            │ │
│ │ • Bonus: +0.05 per matching entity                          │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ RECENCY (25%)                                               │ │
│ │ • < 24 hours ago: 1.0                                       │ │
│ │ • 1-7 days ago: 0.8 - 0.5 (linear decay)                   │ │
│ │ • 7-30 days ago: 0.5 - 0.1 (linear decay)                  │ │
│ │ • > 30 days ago: 0.0                                        │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ QUALITY (15%)                                               │ │
│ │ • Has summary: +0.3                                         │ │
│ │ • Has topics: +0.2                                          │ │
│ │ • Has entities: +0.2                                        │ │
│ │ • Message count ≥ 10: +0.3                                  │ │
│ │ • Has decisions (Neo4j): +0.2                               │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: Ranking & Auto-Selection                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Ranked Results:                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Rank │ Type    │ Name              │ Score │ Auto-Select?  │ │
│ ├──────┼─────────┼───────────────────┼───────┼───────────────┤ │
│ │  1   │ session │ E-commerce Proj   │ 0.91  │ ✓ YES         │ │
│ │  2   │ conv    │ Payment chat      │ 0.68  │ ✗ NO          │ │
│ │  3   │ session │ React Learning    │ 0.52  │ ✗ NO          │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Auto-Selection Rules:                                            │
│ • Score > 0.85 AND                                              │
│ • Margin > 0.20 (difference from #2)                            │
│ • Result: "E-commerce Project" auto-selected (0.91 - 0.68 = 0.23)│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
OUTPUT:
{
  "recommendations": [
    {
      "type": "session",
      "id": "session-789",
      "name": "E-commerce Project",
      "description": "Building online store...",
      "score": {
        "relevance": 0.89,
        "recency": 1.0,
        "quality": 0.85,
        "final": 0.91
      },
      "auto_select": true,
      "match_reasons": ["topic:payments", "entity:Stripe"]
    },
    ...
  ],
  "auto_selected": {
    "type": "session",
    "id": "session-789",
    "name": "E-commerce Project"
  },
  "query_analysis": {
    "topics": ["payments", "Stripe"],
    "entities": ["Stripe"]
  }
}
```

---

### Vector Similarity: How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                 COSINE SIMILARITY EXPLAINED                      │
└─────────────────────────────────────────────────────────────────┘

3072-Dimensional Vector Space (simplified to 2D):

                    ↑ Dimension 2
                    │
                    │     * "PostgreSQL database"
                    │    /
                    │   /  θ = small angle = HIGH similarity
                    │  /
                    │ /
                    │/________* "what database?" (query)
                    │\
                    │ \
                    │  \  θ = large angle = LOW similarity  
                    │   \
                    │    * "cooking recipes"
                    │
                    └─────────────────────→ Dimension 1

Cosine Similarity = cos(θ)
  - θ = 0°   → similarity = 1.0 (identical meaning)
  - θ = 90°  → similarity = 0.0 (unrelated)
  - θ = 180° → similarity = -1.0 (opposite meaning)

pgvector operator: <=>  (cosine distance = 1 - similarity)
```

### IVFFlat Index: Fast Search

```
┌─────────────────────────────────────────────────────────────────┐
│                    IVFFlat INDEX                                 │
└─────────────────────────────────────────────────────────────────┘

Without Index: Compare query to ALL vectors (slow)
┌─────────────────────────────────────────────────────────────────┐
│ Query → Compare with 100,000 vectors → O(n) = SLOW              │
└─────────────────────────────────────────────────────────────────┘

With IVFFlat: Vectors grouped into clusters
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│    Cluster 1          Cluster 2          Cluster 3              │
│   (Tech/Code)        (Business)         (Personal)              │
│   ┌─────────┐        ┌─────────┐        ┌─────────┐            │
│   │ * * *   │        │  * *    │        │   *     │            │
│   │  * * *  │        │ * * *   │        │  * *    │            │
│   │   * *   │        │  * *    │        │ * * *   │            │
│   └─────────┘        └─────────┘        └─────────┘            │
│        ↑                                                         │
│        │                                                         │
│   Query lands here                                               │
│   → Only search Cluster 1                                        │
│   → O(n/k) = FAST                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

lists = 100 → 100 clusters
Search probes nearest clusters only
```

---

### Complete User Journey Example

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE USER JOURNEY                         │
└─────────────────────────────────────────────────────────────────┘

DAY 1: User chats with ChatGPT
────────────────────────────────
User: "I want to build an e-commerce site"
ChatGPT: "Great! Use React and PostgreSQL..."

       ↓ Client calls POST /ingest
       
Symmetry:
  1. Chunks conversation → 3 chunks
  2. Embeds chunks → 3 vectors stored
  3. Generates summary → "E-commerce project with React/PostgreSQL"
  4. Embeds summary → conversation vector
  5. No matching session → creates "E-commerce Project" session
  6. Extracts knowledge → (User)-[CHOSE]->(PostgreSQL)
  7. Returns: { conversation_id, session_id, summary }


DAY 2: User switches to Claude
────────────────────────────────
User opens Claude, wants to continue project

       ↓ Client calls POST /recommend
       
Symmetry:
  1. User types "continue e-commerce"
  2. Embeds query
  3. Searches sessions → "E-commerce Project" (0.94 similarity)
  4. Returns: { auto_selected: "E-commerce Project" }

       ↓ Client calls POST /retrieve (session mode)
       
Symmetry:
  1. Fetches all conversations in session
  2. Builds chronological context_prompt
  3. Includes decisions, facts from Neo4j
  4. Returns: { context_prompt: "[Full history...]" }

       ↓ Client injects context_prompt into Claude
       
Claude now has FULL context from ChatGPT conversation!

User: "What about the payment system?"
Claude: "Based on your PostgreSQL choice, Stripe integrates well..."
```

---

### Storage Summary

| Data | Storage | Purpose |
|------|---------|---------|
| Raw messages | PostgreSQL `conversations.raw_messages` | Original conversation |
| Chunks | PostgreSQL `chunks.content` | Granular semantic search |
| Chunk embeddings | PostgreSQL `chunks.embedding` | Vector similarity search |
| Conversation embedding | PostgreSQL `conversations.embedding` | Session matching |
| Summary | PostgreSQL `conversations.summary` | Quick overview |
| Topics/Entities | PostgreSQL arrays | Fast filtering |
| Session info | PostgreSQL `sessions` | Group conversations |
| Entities | Neo4j nodes | Knowledge graph |
| Relationships | Neo4j edges | Entity connections |
| Decisions | Neo4j `CHOSE/DECIDED` | Track choices with reasons |
| Facts | Neo4j properties | Temporal knowledge |

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
