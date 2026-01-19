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
3. [Architecture Overview](#-architecture-overview)
4. [Quick Start](#-quick-start)
5. [Deep Dive: System Layers](#-deep-dive-system-layers)
   - [API Layer](#1-api-layer)
   - [Service Layer](#2-service-layer)
   - [Data Layer](#3-data-layer)
6. [Core Pipelines](#-core-pipelines)
   - [Ingestion Pipeline](#ingestion-pipeline)
   - [Retrieval Pipeline](#retrieval-pipeline)
   - [Recommendation Pipeline](#recommendation-pipeline)
7. [Key Algorithms & Techniques](#-key-algorithms--techniques)
8. [Data Models](#-data-models)
9. [API Reference](#-api-reference)
10. [Configuration](#-configuration)
11. [Project Structure](#-project-structure)

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
| **Contradiction Detection** | Warns when you contradict past decisions |

---

## 🏗️ Architecture Overview

Symmetry uses a **layered architecture** with two main data stores:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SYMMETRY SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│   │ ChatGPT │  │ Claude  │  │ Cursor  │  │  Other  │    ← AI Clients        │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘                        │
│        └────────────┴────────────┴────────────┘                              │
│                          │                                                   │
│                          ▼                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                        API LAYER (FastAPI)                            │  │
│   │  /ingest  /retrieve  /recommend  /sessions  /users  /knowledge       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                          │                                                   │
│                          ▼                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                       SERVICE LAYER                                   │  │
│   │  ChunkingService    EmbeddingService    ExtractionService            │  │
│   │  SessionService     RecommendationService    SummarizationService    │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                          │                                                   │
│            ┌─────────────┴─────────────┐                                    │
│            ▼                           ▼                                    │
│   ┌─────────────────────┐   ┌─────────────────────┐                        │
│   │    MEMORY LAYER     │   │   KNOWLEDGE LAYER   │                        │
│   │                     │   │                     │                        │
│   │   PostgreSQL +      │   │      Neo4j          │                        │
│   │   pgvector          │   │   (Graph DB)        │                        │
│   │                     │   │                     │                        │
│   │ • Users             │   │ • Entities          │                        │
│   │ • Sessions          │   │ • Relationships     │                        │
│   │ • Conversations     │   │ • Decisions         │                        │
│   │ • Chunks            │   │ • Facts             │                        │
│   │ • Embeddings        │   │                     │                        │
│   └─────────────────────┘   └─────────────────────┘                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Two Databases?

| Database | Purpose | Strength |
|----------|---------|----------|
| **PostgreSQL + pgvector** | Memory Layer | Fast vector similarity search, relational data, ACID compliance |
| **Neo4j** | Knowledge Layer | Graph traversal, relationship queries, entity connections |

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/symmetry-mvp.git
cd symmetry-mvp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

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

**Neo4j (Optional but recommended):**
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

## 🔬 Deep Dive: System Layers

### 1. API Layer

**Location:** `app/api/routes/`

The API layer handles HTTP requests and responses using FastAPI. Each route file handles a specific domain:

```
app/api/routes/
├── users.py          # User registration, authentication
├── ingest.py         # Store conversations (POST /ingest)
├── retrieve.py       # Get context (POST /retrieve)
├── recommend.py      # Get recommendations (POST /recommend)
├── sessions.py       # Session management (CRUD)
├── conversations.py  # Conversation management
├── memories.py       # Memory operations
└── knowledge.py      # Knowledge graph operations
```

#### Key Concepts:

**Dependency Injection (`app/api/dependencies.py`):**
```python
# Every route gets these injected automatically:
user_id: str = Depends(get_current_user_id)      # From API key
postgres: PostgresDB = Depends(get_postgres)      # Database connection
neo4j: Neo4jDB = Depends(get_neo4j)              # Graph database
config: Settings = Depends(get_config)            # App settings
```

**Authentication:**
- All endpoints require `Authorization: Bearer sk_your_api_key` header
- API key is validated against the `users` table
- User ID is extracted and passed to all operations

---

### 2. Service Layer

**Location:** `app/services/`

The service layer contains the core business logic. Each service is a focused module:

```
app/services/
├── chunking.py       # Text splitting with semantic awareness
├── embedding.py      # Vector embedding generation
├── extraction.py     # Knowledge extraction from text
├── session.py        # Session detection and linking
├── recommendation.py # Recommendation scoring algorithm
└── summarization.py  # Context summary generation
```

#### 2.1 Chunking Service (`chunking.py`)

**Purpose:** Split conversations into smaller pieces for embedding while preserving meaning.

**Key Innovation: Semantic-Aware Chunking**

Unlike simple character-based splitting, Symmetry's chunker:

1. **Splits at sentence boundaries** - Never cuts mid-thought
2. **Preserves negations** - "NOT going to use X" stays together
3. **Keeps decisions with reasons** - "I chose X because Y" stays together
4. **Protects code blocks** - Never splits code
5. **Message-aware** - Prefers splitting between USER/ASSISTANT messages

```python
# Bad chunking (character-based):
Chunk 1: "I'm NOT going to use Mon"
Chunk 2: "goDB because it lacks ACID"  # Lost the negation context!

# Good chunking (semantic-aware):
Chunk 1: "I'm NOT going to use MongoDB because it lacks ACID compliance."
```

**Decision Boundary Detection:**

The chunker identifies patterns that shouldn't be split:

```python
# Positive decisions
"I'll use", "I decided", "going with", "let's use"

# Negative decisions (CRITICAL - keeps negation with subject)
"NOT going to", "won't use", "decided against", "ruled out"

# Comparisons
"better than", "prefer X over", "instead of"

# Conclusions
"because", "therefore", "the reason is"
```

**Chunking Modes:**

| Mode | Function | Use Case |
|------|----------|----------|
| `chunk_conversation_semantic()` | Semantic-aware splitting | Default, recommended |
| `chunk_by_exchange()` | User-Assistant pairs | Keep Q&A together |
| `chunk_with_context()` | Chunks with surrounding context | Better retrieval |

---

#### 2.2 Embedding Service (`embedding.py`)

**Purpose:** Convert text into vector representations for semantic search.

**How It Works:**

```
Text: "I chose PostgreSQL for my e-commerce project"
         │
         ▼
    OpenAI/Azure API (text-embedding-3-large)
         │
         ▼
Vector: [0.0234, -0.0891, 0.1456, ..., 0.0023]  (3072 floats)
```

**Why Embeddings?**

Embeddings capture **semantic meaning**, not just keywords:

```
Query: "What database did I pick?"
         ↓ Similar vector to:
Stored: "I chose PostgreSQL for the project"

Even though "pick" ≠ "chose" and "database" ≠ "PostgreSQL",
the vectors are close because the MEANING is similar.
```

**Configuration:**

| Setting | Default | Description |
|---------|---------|-------------|
| `embedding_model` | text-embedding-3-large | OpenAI model |
| `embedding_dimensions` | 3072 | Vector size |
| `provider` | azure_openai | OpenAI or Azure |

---

#### 2.3 Extraction Service (`extraction.py`)

**Purpose:** Extract structured knowledge (entities, relationships, decisions) from conversations.

**What Gets Extracted:**

```
Conversation: "I'll use PostgreSQL. My colleague suggested MongoDB but I ruled it out."
                                    │
                                    ▼
                            LLM Analysis (GPT-4o-mini)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ENTITIES:                                                                    │
│   • PostgreSQL (Tool) - "Relational database"                               │
│   • MongoDB (Tool) - "NoSQL database"                                       │
│                                                                              │
│ RELATIONSHIPS:                                                               │
│   • User ──CHOSE──→ PostgreSQL (confidence: 0.95, status: decided)          │
│   • User ──REJECTED──→ MongoDB (confidence: 0.85, status: rejected)         │
│   • User ──CONSIDERING──→ MongoDB (attributed_to: colleague)                │
│                                                                              │
│ FACTS:                                                                       │
│   • User WORKS_ON E-commerce Project (temporal: current)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Decision Status Classification:**

| User Says | Status | Type | Confidence |
|-----------|--------|------|------------|
| "I'll use X", "I decided on X" | decided | CHOSE | 0.85-1.0 |
| "I think X", "Leaning toward X" | exploring | CONSIDERING | 0.5-0.7 |
| "Maybe X", "What about X?" | exploring | CONSIDERING | 0.3-0.5 |
| "I won't use X", "Ruled out X" | rejected | REJECTED | 0.8-1.0 |

**Critical: Negation Detection**

The extraction prompt is specifically designed to catch negations:

```python
# These are NOT decisions to USE something:
"I'm NOT going to use MongoDB"     → REJECTED (not CHOSE!)
"I decided against Redis"          → REJECTED
"We ruled out DynamoDB"            → REJECTED
```

**Source Attribution:**

Every extracted relationship tracks WHO said it:

| Source | Meaning |
|--------|---------|
| `user` | The person in the conversation |
| `colleague` | Someone the user mentioned |
| `article` | External documentation/blog |
| `ai_suggestion` | The AI assistant suggested it |

---

#### 2.4 Session Service (`session.py`)

**Purpose:** Automatically detect and link related conversations into sessions.

**How Session Detection Works:**

```
New Conversation: "Help me add Stripe payments to my React store"
                                    │
                                    ▼
                        Generate Conversation Embedding
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SEARCH EXISTING SESSIONS BY SIMILARITY                                       │
│                                                                              │
│ SELECT * FROM sessions                                                       │
│ WHERE 1 - (embedding <=> new_embedding) > 0.5                               │
│ ORDER BY embedding <=> new_embedding                                         │
│ LIMIT 5                                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ RESULTS:                                                                     │
│                                                                              │
│   Session                    │ Similarity │ Recency Boost │ Final Score    │
│   ─────────────────────────────────────────────────────────────────────────│
│   E-commerce Project         │    0.92    │    +0.08      │    0.96  ✓     │
│   React Learning             │    0.71    │    +0.02      │    0.73        │
│   Personal Blog              │    0.45    │    +0.00      │    0.45        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        DECISION LOGIC:
                        
    IF score > 0.85 AND auto_link_session=true:
        → AUTO-LINK (high confidence)
    ELIF score > 0.70:
        → SUGGEST (user confirms)
    ELSE:
        → STANDALONE (no match)
```

**Confidence Thresholds:**

| Confidence | Action | User Control |
|------------|--------|--------------|
| > 85% | Auto-link (if enabled) | `auto_link_session: true` |
| 70-85% | Suggest to user | User must confirm |
| < 70% | Keep standalone | No suggestion |

**Recency Boost:**

Recent sessions get a score boost to prefer active projects:

```python
if hours_ago <= 24:
    recency_boost = 0.1 * (1 - hours_ago / 24)
else:
    recency_boost = 0.0
```

---

#### 2.5 Recommendation Service (`recommendation.py`)

**Purpose:** Find relevant context before starting a new conversation.

**Scoring Algorithm:**

```
Final Score = (Relevance × 0.60) + (Recency × 0.25) + (Quality × 0.15)
```

**Relevance Score (60%):**
```
Base: Cosine similarity from embedding search
Bonus: +0.1 per matching topic
Bonus: +0.05 per matching entity
```

**Recency Score (25%):**
```
< 24 hours ago:  1.0
1-7 days ago:    0.8 → 0.5 (linear decay)
7-30 days ago:   0.5 → 0.1 (linear decay)
> 30 days ago:   0.0
```

**Quality Score (15%):**
```
Has summary:     +0.3
Has topics:      +0.2
Has entities:    +0.2
Messages ≥ 10:   +0.3
Has decisions:   +0.2 (from Neo4j)
```

**Auto-Selection:**

A recommendation is auto-selected if:
1. Score > 0.85 **AND**
2. Margin > 0.20 (gap from second-best)

```python
if top.score > 0.85 and (top.score - second.score) > 0.20:
    auto_select = top
```

**Knowledge Graph Expansion:**

The recommendation service uses Neo4j to expand queries:

```
User Query: "implement caching"
         │
         ▼
    Extract Keywords: ["caching"]
         │
         ▼
    Neo4j Graph Traversal:
    caching → Redis → session storage → TTL
         │
         ▼
    Expanded Search Terms: ["caching", "Redis", "session storage", "TTL"]
```

---

#### 2.6 Summarization Service (`summarization.py`)

**Purpose:** Generate human-readable summaries from retrieved context.

**Input:**
- Query (what user is asking about)
- Chunks (relevant conversation snippets)
- Decisions (from Neo4j)
- Facts (from Neo4j)
- Entities (from Neo4j)

**Output:**
```
"You chose PostgreSQL for your e-commerce project because you need 
relational data for products, orders, and users. Prisma was recommended 
as the ORM. You're using React for the frontend and considering Stripe 
for payments."
```

---

### 3. Data Layer

**Location:** `app/db/`

#### 3.1 PostgreSQL Client (`postgres.py`)

**Purpose:** Handle all Memory Layer operations.

**Key Operations:**

| Category | Methods |
|----------|---------|
| **Users** | `create_user()`, `get_user_by_api_key()`, `get_user_by_email()` |
| **Sessions** | `create_session()`, `get_session()`, `list_sessions()`, `search_sessions_by_embedding()` |
| **Conversations** | `create_conversation()`, `get_conversation()`, `link_conversation_to_session()` |
| **Chunks** | `create_chunk()`, `search_chunks()`, `search_chunks_hybrid()` |
| **Suggestions** | `create_session_suggestion()`, `get_session_suggestion_stats()` |

**Vector Search with pgvector:**

```sql
-- Cosine similarity search
SELECT content, 1 - (embedding <=> query_embedding) as similarity
FROM chunks
WHERE user_id = $user_id
  AND 1 - (embedding <=> query_embedding) > 0.5
ORDER BY embedding <=> query_embedding
LIMIT 5
```

**Hybrid Search (Semantic + Keyword):**

```python
async def search_chunks_hybrid(user_id, embedding, keywords, semantic_weight=0.7):
    """
    Combines:
    - Semantic similarity (70%): Vector cosine distance
    - Keyword matching (30%): ILIKE text search
    
    Helps catch cases where:
    - Semantic search misses due to vocabulary mismatch
    - Keywords catch what embeddings miss
    """
```

**Tiered Confidence Results:**

```python
async def search_chunks_tiered(user_id, embedding, limit=10):
    """
    Returns results in confidence tiers:
    - High (≥0.7): Very relevant
    - Medium (0.5-0.7): Possibly relevant  
    - Low (0.3-0.5): Might be related
    """
```

---

#### 3.2 Neo4j Client (`neo4j.py`)

**Purpose:** Handle all Knowledge Layer operations.

**Graph Structure:**

```
         (User)
           │
     ┌─────┴─────┬──────────┐
     │           │          │
   CHOSE     REJECTED   CONSIDERING
     │           │          │
     ▼           ▼          ▼
(PostgreSQL) (MongoDB)   (Redis)
     │
   USED_FOR
     │
     ▼
(E-commerce Project)
     │
  ┌──┴──┐
USES   INTEGRATES
  │       │
  ▼       ▼
(React) (Stripe)
```

**Key Operations:**

| Category | Methods |
|----------|---------|
| **Entities** | `create_entity()`, `get_entities()`, `find_related_entities()` |
| **Relationships** | `create_relationship()`, `get_decisions()`, `get_exploring()`, `get_rejected()` |
| **Facts** | `create_temporal_fact()`, `get_current_facts()` |
| **Validation** | `detect_contradictions()`, `verify_relationship()`, `get_unverified_knowledge()` |

**Relationship Properties:**

```python
{
    "id": "uuid",
    "created_at": "2026-01-19T10:30:00Z",
    "confidence": 0.9,           # 0.0-1.0
    "status": "decided",         # decided, exploring, rejected
    "verified": False,           # User hasn't verified yet
    "attributed_to": "user",     # user, colleague, article, ai_suggestion
    "temporal": "current",       # current, past, future
    "conversation_id": "...",    # Source conversation
    "source": "chatgpt"          # Source platform
}
```

**Contradiction Detection:**

```cypher
// Find cases where user chose something, then chose something else in same category
MATCH (u:User {user_id: $user_id})-[r1:CHOSE]->(t1)
MATCH (u)-[r2:CHOSE]->(t2)
WHERE t1 <> t2
AND labels(t1) = labels(t2)  // Same category (both databases, both frameworks, etc.)
AND r1.created_at < r2.created_at
RETURN t1.name as old_decision, t2.name as new_decision, labels(t1)[0] as category
```

---

## 🔄 Core Pipelines

### Ingestion Pipeline

**Endpoint:** `POST /api/v1/ingest`

**Complete Flow:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT:
{
  "source": "chatgpt",
  "messages": [
    {"role": "user", "content": "I want to build an e-commerce site..."},
    {"role": "assistant", "content": "Great! Let's use React and..."}
  ],
  "auto_link_session": true
}
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: GENERATE SUMMARY                                                     │
│                                                                              │
│ LLM (GPT-4o-mini) analyzes conversation:                                    │
│   → Summary: "User building e-commerce with React, chose PostgreSQL"        │
│   → Topics: ["e-commerce", "React", "PostgreSQL"]                           │
│   → Entities: ["React", "PostgreSQL", "Stripe"]                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: GENERATE CONVERSATION EMBEDDING                                      │
│                                                                              │
│ Summary text → text-embedding-3-large → [3072-dim vector]                   │
│ This embedding represents the ENTIRE conversation's meaning                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: SESSION DETECTION                                                    │
│                                                                              │
│ Search existing sessions by embedding similarity:                            │
│                                                                              │
│   E-commerce Project    │ 0.96 similarity │ AUTO-LINK ✓                     │
│   React Learning        │ 0.73 similarity │                                  │
│   Personal Blog         │ 0.45 similarity │                                  │
│                                                                              │
│ Decision: Auto-link to "E-commerce Project" (0.96 > 0.85 threshold)         │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: STORE CONVERSATION                                                   │
│                                                                              │
│ INSERT INTO conversations (user_id, source, raw_messages, session_id,       │
│                            summary, topics, entities, embedding)            │
│ VALUES (...)                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: CHUNK AND EMBED                                                      │
│                                                                              │
│ Semantic Chunking:                                                           │
│   "USER: I want to build..."  →  Chunk 0 (preserves meaning)                │
│   "ASSISTANT: Great! Let's..." →  Chunk 1 (keeps Q&A context)               │
│                                                                              │
│ Each chunk → Embedding API → Store in chunks table                          │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: EXTRACT KNOWLEDGE (Neo4j)                                            │
│                                                                              │
│ LLM extracts structured knowledge:                                           │
│                                                                              │
│   ENTITIES:                                                                  │
│     • PostgreSQL (Tool)                                                      │
│     • React (Technology)                                                     │
│     • E-commerce Project (Project)                                           │
│                                                                              │
│   RELATIONSHIPS:                                                             │
│     • User ──CHOSE──→ PostgreSQL (confidence: 0.95)                         │
│     • User ──CHOSE──→ React (confidence: 0.90)                              │
│     • Project ──USES──→ PostgreSQL                                          │
│                                                                              │
│   FACTS:                                                                     │
│     • User WORKS_ON E-commerce Project (temporal: current)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: UPDATE SESSION EMBEDDING                                             │
│                                                                              │
│ Recalculate session embedding as average of all conversation embeddings     │
│ This improves future session matching accuracy                               │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
OUTPUT:
{
  "conversation_id": "conv-123",
  "chunks_created": 4,
  "entities_extracted": 3,
  "relationships_created": 3,
  "linked_session_id": "session-456",
  "session_suggestion": {
    "suggested_session": {"name": "E-commerce Project"},
    "confidence": 0.96,
    "auto_linked": true
  }
}
```

**Append Mode:**

When updating an existing conversation:

```python
# Option 1: Send ALL messages (default)
{
  "conversation_id": "conv-123",
  "messages": [old_msg1, old_msg2, new_msg3, new_msg4],  # ALL messages
  "append_only": false  # System compares to find new ones
}

# Option 2: Send ONLY new messages
{
  "conversation_id": "conv-123", 
  "messages": [new_msg3, new_msg4],  # ONLY new messages
  "append_only": true  # System appends directly
}
```

---

### Retrieval Pipeline

**Endpoint:** `POST /api/v1/retrieve`

**Four Modes:**

| Mode | Use Case | Required Params |
|------|----------|-----------------|
| `query` | Find specific info | `query` |
| `session` | Continue a project | `session_id` |
| `conversation` | Continue specific chat | `conversation_id` |
| `full` | Get ALL context | - |

**Query Mode Flow:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     QUERY MODE RETRIEVAL                                     │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT: { "mode": "query", "query": "what database did I choose?" }
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: EXTRACT KEYWORDS                                                     │
│                                                                              │
│ Query: "what database did I choose?"                                        │
│ Keywords: ["database", "choose"]                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: KNOWLEDGE GRAPH EXPANSION (Neo4j)                                    │
│                                                                              │
│ Find related entities from user's graph:                                    │
│   "database" → PostgreSQL → ACID, relational, Prisma                        │
│                                                                              │
│ Expanded terms: ["database", "choose", "PostgreSQL", "ACID", "Prisma"]      │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: GENERATE QUERY EMBEDDING                                             │
│                                                                              │
│ "what database did I choose?" → [3072-dim vector]                           │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: HYBRID SEARCH                                                        │
│                                                                              │
│ Combines:                                                                    │
│   • Semantic: Vector similarity (70% weight)                                │
│   • Keyword: Text matching on expanded terms (30% weight)                   │
│                                                                              │
│ Results:                                                                     │
│   1. "I recommend PostgreSQL because..."  (combined: 0.91)                  │
│   2. "PostgreSQL is great for relational..."  (combined: 0.87)              │
│   3. "You'll need tables for products..."  (combined: 0.82)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: FETCH KNOWLEDGE (Neo4j)                                              │
│                                                                              │
│ Decisions: [PostgreSQL (CHOSE, confidence: 0.95)]                           │
│ Facts: [User WORKS_ON E-commerce Project]                                   │
│ Entities: [PostgreSQL, React, Stripe]                                       │
│ Contradictions: [] (none detected)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: BUILD CONTEXT PROMPT                                                 │
│                                                                              │
│ [CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]             │
│                                                                              │
│ ## ✅ Confirmed Decisions:                                                   │
│ - PostgreSQL (Reason: ACID compliance, relational data needs)               │
│                                                                              │
│ ## Current Facts:                                                            │
│ - User WORKS_ON E-commerce Project                                          │
│                                                                              │
│ ## Relevant Past Discussions:                                                │
│ - "I recommend PostgreSQL because you need relational data..."              │
│                                                                              │
│ [END SYMMETRY CONTEXT]                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: GENERATE SUMMARY                                                     │
│                                                                              │
│ LLM creates human-readable summary:                                          │
│ "You chose PostgreSQL for your e-commerce project because you need          │
│  relational data for products, orders, and users."                          │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
OUTPUT:
{
  "summary": "You chose PostgreSQL for your e-commerce project...",
  "context_prompt": "[CONTEXT FROM PREVIOUS AI CONVERSATIONS...]",
  "decisions": [{"content": "PostgreSQL", "reason": "ACID compliance"}],
  "facts": [{"subject": "User", "predicate": "WORKS_ON", "object": "E-commerce"}],
  "entities": ["PostgreSQL", "React", "Stripe"],
  "chunks_found": 3
}
```

**Session Mode:**

Returns ALL conversations in a session in chronological order:

```
[CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]

## Session: E-commerce Project
Description: Building online store with React/Node/PostgreSQL

## Complete Session History (chronological):

### [chatgpt] - 2026-01-15
**USER**: I want to build an e-commerce site...
**ASSISTANT**: Great! Let's start with the tech stack...

### [claude] - 2026-01-16
**USER**: Help me design the database schema...
**ASSISTANT**: For e-commerce, you need these tables...

### [cursor] - 2026-01-17
**USER**: Now let's integrate Stripe...
**ASSISTANT**: Here's how to set up Stripe...

## ✅ Confirmed Decisions:
- PostgreSQL (Reason: relational data needs)
- React (Reason: component-based UI)
- Stripe (Reason: best payment docs)

[END SYMMETRY CONTEXT]
```

---

### Recommendation Pipeline

**Endpoint:** `POST /api/v1/recommend`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RECOMMENDATION PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT: { "query": "implement Stripe payments" }
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: ANALYZE QUERY                                                        │
│                                                                              │
│ Extract topics: ["payments", "Stripe", "implementation"]                    │
│ Extract entities: ["Stripe"]                                                │
│ Generate embedding: [3072-dim vector]                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: KNOWLEDGE GRAPH EXPANSION                                            │
│                                                                              │
│ Neo4j traversal from "Stripe", "payments":                                  │
│   Stripe → E-commerce Project → PostgreSQL → products table                 │
│                                                                              │
│ Expanded entities: ["Stripe", "E-commerce Project", "checkout"]             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: SEARCH SESSIONS & CONVERSATIONS                                      │
│                                                                              │
│ Sessions (by embedding similarity):                                          │
│   E-commerce Project │ similarity: 0.89                                     │
│   React Learning     │ similarity: 0.52                                     │
│                                                                              │
│ Standalone Conversations (not in sessions):                                  │
│   Payment discussion │ similarity: 0.68                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: SCORE AND RANK                                                       │
│                                                                              │
│ For each candidate:                                                          │
│   Relevance = similarity + topic_bonus + entity_bonus                       │
│   Recency = time_decay_function(last_activity)                              │
│   Quality = has_summary + has_topics + message_count                        │
│                                                                              │
│   Final = (Relevance × 0.60) + (Recency × 0.25) + (Quality × 0.15)         │
│                                                                              │
│ Results:                                                                     │
│   E-commerce Project │ final: 0.91 │ AUTO-SELECT ✓                          │
│   Payment discussion │ final: 0.68 │                                        │
│   React Learning     │ final: 0.52 │                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
OUTPUT:
{
  "recommendations": [
    {
      "type": "session",
      "name": "E-commerce Project",
      "score": {"relevance": 0.89, "recency": 1.0, "quality": 0.85, "final": 0.91},
      "auto_select": true
    },
    ...
  ],
  "auto_selected": {"type": "session", "name": "E-commerce Project"},
  "query_analysis": {"topics": ["payments", "Stripe"], "entities": ["Stripe"]}
}
```

---

## 🧠 Key Algorithms & Techniques

### 1. Vector Similarity Search

**Cosine Similarity:**

```
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
```

**pgvector Operator:**
```sql
-- <=> is cosine distance (1 - similarity)
SELECT 1 - (embedding <=> query_embedding) as similarity
FROM chunks
ORDER BY embedding <=> query_embedding
```

### 2. IVFFlat Index

**Problem:** Comparing query to ALL vectors is O(n) - slow!

**Solution:** Cluster vectors, only search relevant clusters:

```
Without Index:
  Query → Compare with 100,000 vectors → O(n) = SLOW

With IVFFlat (100 clusters):
  Query → Find nearest cluster → Search ~1,000 vectors → O(n/k) = FAST

CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 3. Semantic-Aware Chunking

**Key Patterns Protected from Splitting:**

```python
# Negations (CRITICAL)
"NOT going to", "won't use", "decided against"

# Decisions with reasons
"because", "therefore", "the reason is"

# Comparisons
"better than", "prefer X over", "instead of"

# Code blocks
```code``` markers, inline `code`

# Lists
"first", "second", "1.", "2."
```

### 4. Session Detection Algorithm

```python
def detect_session(conversation_embedding, user_sessions):
    # 1. Vector similarity search
    similar_sessions = search_by_embedding(conversation_embedding)
    
    # 2. Add recency boost
    for session in similar_sessions:
        if session.last_activity < 24_hours_ago:
            session.score += 0.1 * (1 - hours_ago / 24)
    
    # 3. Apply decision rules
    top = similar_sessions[0]
    second = similar_sessions[1] if len > 1 else None
    
    if top.score > 0.85 and (not second or top.score - second.score > 0.15):
        return AutoLink(top)
    elif top.score > 0.70:
        return Suggest(top)
    else:
        return Standalone()
```

### 5. Knowledge Graph Expansion

```cypher
// Find entities related to search terms
UNWIND $search_terms AS term
MATCH (start)
WHERE start.user_id = $user_id
AND toLower(start.name) CONTAINS toLower(term)

// Traverse 1-2 hops to find related entities
MATCH path = (start)-[*1..2]-(related)
WHERE related.user_id = $user_id

RETURN DISTINCT related.name
ORDER BY length(path) ASC, COUNT(*) DESC
LIMIT 10
```

---

## 📊 Data Models

### PostgreSQL Schema

```sql
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
├── has_decisions (BOOLEAN)
├── has_facts (BOOLEAN)
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

### Neo4j Graph Model

```
Node Types:
├── User          {user_id}
├── Tool          {name, description}
├── Technology    {name, description}
├── Project       {name, description}
├── Company       {name}
└── Concept       {name}

Relationship Types:
├── CHOSE         {confidence, status, reason, verified, temporal}
├── REJECTED      {confidence, reason}
├── CONSIDERING   {confidence, attributed_to}
├── PREFERS       {strength, reason}
├── USES          {temporal}
├── WORKS_ON      {valid_from, valid_to}
└── RELATED_TO    {description}
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
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
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
  -d '{"mode": "query", "query": "what database did I choose?"}'

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

# Azure OpenAI - Chat
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Azure OpenAI - Embeddings
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://...
AZURE_OPENAI_EMBEDDING_API_KEY=...
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Settings
CHUNK_SIZE=500
CHUNK_OVERLAP=50
SIMILARITY_THRESHOLD=0.7
```

### Configuration Class (`app/config.py`)

```python
class Settings(BaseSettings):
    # Database
    supabase_url: str
    supabase_key: str
    database_url: str
    
    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    # LLM
    llm_provider: str = "openai"
    openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    
    # App settings
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o-mini"
    similarity_threshold: float = 0.7
```

---

## 📁 Project Structure

```
symmetry-mvp-v2/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py        # Dependency injection (auth, DB)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── users.py           # User registration
│   │       ├── ingest.py          # POST /ingest
│   │       ├── retrieve.py        # POST /retrieve
│   │       ├── recommend.py       # POST /recommend
│   │       ├── sessions.py        # Session CRUD
│   │       ├── conversations.py   # Conversation management
│   │       ├── memories.py        # Memory operations
│   │       └── knowledge.py       # Knowledge graph operations
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── postgres.py            # PostgreSQL client (Memory Layer)
│   │   └── neo4j.py               # Neo4j client (Knowledge Layer)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chunking.py            # Semantic text chunking
│   │   ├── embedding.py           # Vector embedding generation
│   │   ├── extraction.py          # Knowledge extraction (LLM)
│   │   ├── session.py             # Session detection & linking
│   │   ├── recommendation.py      # Recommendation scoring
│   │   └── summarization.py       # Context summarization
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py            # Pydantic request models
│   │   └── responses.py           # Pydantic response models
│   │
│   └── prompts/
│       ├── __init__.py
│       ├── extraction.py          # Knowledge extraction prompts
│       └── summarization.py       # Summarization prompts
│
├── scripts/
│   ├── setup_db.sql               # PostgreSQL schema
│   ├── migrate_db.sql             # Migration scripts
│   └── setup_neo4j.cypher         # Neo4j schema
│
├── tests/
│   ├── __init__.py
│   ├── test_chunking.py           # Chunking service tests
│   └── test_verification.py       # Verification tests
│
├── requirements.txt               # Python dependencies
├── env.example                    # Environment template
├── Dockerfile                     # Container definition
└── README.md                      # This file
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

## 🎓 Learning Resources

### Understanding Embeddings
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- Embeddings capture semantic meaning, not just keywords
- Similar meanings → similar vectors → close in vector space

### Understanding pgvector
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- `<=>` operator = cosine distance
- IVFFlat index for fast approximate nearest neighbor search

### Understanding Neo4j
- [Neo4j Graph Database](https://neo4j.com/docs/)
- Nodes = Entities, Edges = Relationships
- Cypher query language for graph traversal

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Symmetry</strong> — Never lose context again.
</p>
