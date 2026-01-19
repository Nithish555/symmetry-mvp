"""
Symmetry MVP - Main FastAPI Application

The Context OS for AI-Native Work.
Provides persistent memory and knowledge across AI tools.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import ingest, retrieve, memories, users, conversations, sessions, recommend, knowledge
from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    settings = get_settings()
    
    # Initialize database connections
    app.state.postgres = PostgresDB(settings.database_url)
    app.state.neo4j = Neo4jDB(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password
    )
    
    # Try to connect to databases
    try:
        logger.info("Connecting to PostgreSQL...")
        await app.state.postgres.connect()
        logger.info("PostgreSQL connected!")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        app.state.postgres = None
    
    try:
        logger.info("Connecting to Neo4j...")
        await app.state.neo4j.connect()
        logger.info("Neo4j connected!")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        app.state.neo4j = None
    
    yield
    
    # Cleanup on shutdown
    if app.state.postgres:
        await app.state.postgres.disconnect()
        logger.info("PostgreSQL disconnected")
    if app.state.neo4j:
        await app.state.neo4j.disconnect()
        logger.info("Neo4j disconnected")


app = FastAPI(
    title="Symmetry API",
    description="""
## Context OS for AI-Native Work

Symmetry provides a persistent memory and knowledge layer across AI tools,
enabling seamless conversation continuity across different LLMs.

### Key Features

- **Memory Layer**: Store and retrieve conversations with semantic search
- **Knowledge Layer**: Extract and query entities, relationships, and facts
- **Session Management**: Group related conversations across different LLMs
- **Smart Recommendations**: Find relevant context based on your query

### Core Endpoints

- `POST /api/v1/ingest` - Store a conversation
- `POST /api/v1/retrieve` - Get context for a query
- `POST /api/v1/recommend` - Find relevant conversations/sessions

### Session Management

- `POST /api/v1/sessions` - Create a session
- `GET /api/v1/sessions` - List sessions
- `POST /api/v1/sessions/confirm-link` - Confirm session linking
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(ingest.router, prefix="/api/v1", tags=["Ingest"])
app.include_router(retrieve.router, prefix="/api/v1", tags=["Retrieve"])
app.include_router(recommend.router, prefix="/api/v1", tags=["Recommend"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["Conversations"])
app.include_router(memories.router, prefix="/api/v1/memories", tags=["Memories"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "Symmetry API",
        "version": "1.0.0",
        "status": "healthy",
        "description": "Context OS for AI-Native Work"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    postgres_status = "up" if app.state.postgres and app.state.postgres.pool else "down"
    neo4j_status = "up" if app.state.neo4j and app.state.neo4j.driver else "down"
    
    overall = "healthy" if postgres_status == "up" and neo4j_status == "up" else "degraded"
    
    return {
        "status": overall,
        "components": {
            "api": "up",
            "database": postgres_status,
            "knowledge_graph": neo4j_status
        },
        "version": "1.0.0"
    }
