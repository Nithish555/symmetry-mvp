"""
PostgreSQL database client using asyncpg.
Handles Memory Layer: users, sessions, conversations, chunks.
"""

import asyncpg
from typing import Optional, List
from datetime import datetime
import json


class PostgresDB:
    """PostgreSQL database client for Memory Layer."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10
        )
    
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    # =========================================================================
    # User operations
    # =========================================================================
    
    async def create_user(self, email: str, api_key: str) -> dict:
        """Create a new user."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, api_key)
                VALUES ($1, $2)
                RETURNING id, email, api_key, created_at
                """,
                email, api_key
            )
            return dict(row)
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[dict]:
        """Get user by API key."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, api_key, created_at FROM users WHERE api_key = $1",
                api_key
            )
            return dict(row) if row else None
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, api_key, created_at FROM users WHERE email = $1",
                email
            )
            return dict(row) if row else None
    
    # =========================================================================
    # Session operations
    # =========================================================================
    
    async def create_session(self, user_id: str, name: str, description: str = None) -> dict:
        """Create a new session."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (user_id, name, description)
                VALUES ($1, $2, $3)
                RETURNING id, user_id, name, description, topics, entities, 
                          conversation_count, created_at, updated_at, last_activity
                """,
                user_id, name, description
            )
            result = dict(row)
            result["topics"] = list(result.get("topics") or [])
            result["entities"] = list(result.get("entities") or [])
            return result
    
    async def get_session(self, session_id: str, user_id: str) -> Optional[dict]:
        """Get a session by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, name, description, topics, entities,
                       conversation_count, created_at, updated_at, last_activity
                FROM sessions WHERE id = $1 AND user_id = $2
                """,
                session_id, user_id
            )
            if row:
                result = dict(row)
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def get_session_by_name(self, user_id: str, name: str) -> Optional[dict]:
        """Get a session by name."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, name, description, topics, entities,
                       conversation_count, created_at, updated_at, last_activity
                FROM sessions WHERE user_id = $1 AND LOWER(name) = LOWER($2)
                """,
                user_id, name
            )
            if row:
                result = dict(row)
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def list_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        """List all sessions for a user."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, name, description, topics, entities,
                       conversation_count, created_at, updated_at, last_activity
                FROM sessions WHERE user_id = $1
                ORDER BY last_activity DESC LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset
            )
            results = []
            for row in rows:
                result = dict(row)
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    async def update_session(self, session_id: str, user_id: str, 
                            name: str = None, description: str = None) -> Optional[dict]:
        """Update a session."""
        async with self.pool.acquire() as conn:
            updates = ["updated_at = NOW()"]
            params = [session_id, user_id]
            idx = 3
            if name:
                updates.append(f"name = ${idx}")
                params.append(name)
                idx += 1
            if description is not None:
                updates.append(f"description = ${idx}")
                params.append(description)
            
            row = await conn.fetchrow(
                f"""
                UPDATE sessions SET {', '.join(updates)}
                WHERE id = $1 AND user_id = $2
                RETURNING id, user_id, name, description, topics, entities,
                          conversation_count, created_at, updated_at, last_activity
                """,
                *params
            )
            if row:
                result = dict(row)
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def update_session_embedding(self, session_id: str, user_id: str, 
                                       embedding: List[float]) -> bool:
        """Update session embedding."""
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE sessions SET embedding = $3::vector, updated_at = NOW() WHERE id = $1 AND user_id = $2",
                session_id, user_id, emb_str
            )
            return result == "UPDATE 1"
    
    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET session_id = NULL, session_status = 'standalone' WHERE session_id = $1",
                session_id
            )
            result = await conn.execute(
                "DELETE FROM sessions WHERE id = $1 AND user_id = $2",
                session_id, user_id
            )
            return result == "DELETE 1"
    
    async def search_sessions_by_embedding(self, user_id: str, embedding: List[float],
                                           limit: int = 5, threshold: float = 0.5) -> List[dict]:
        """Search sessions by embedding similarity."""
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, description, topics, entities, conversation_count, 
                       created_at, last_activity,
                       1 - (embedding <=> $1::vector) as similarity
                FROM sessions WHERE user_id = $2 AND embedding IS NOT NULL
                AND 1 - (embedding <=> $1::vector) > $3
                ORDER BY embedding <=> $1::vector LIMIT $4
                """,
                emb_str, user_id, threshold, limit
            )
            results = []
            for row in rows:
                result = dict(row)
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    # =========================================================================
    # Conversation operations
    # =========================================================================
    
    async def create_conversation(self, user_id: str, source: str, raw_messages: List[dict],
                                  session_id: str = None, summary: str = None,
                                  topics: List[str] = None, entities: List[str] = None) -> dict:
        """Create a new conversation."""
        status = 'linked' if session_id else 'standalone'
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (user_id, source, raw_messages, session_id, 
                    summary, topics, entities, session_status, message_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, user_id, source, raw_messages, session_id, summary, topics, 
                          entities, session_status, message_count, has_decisions, has_facts, 
                          created_at, updated_at
                """,
                user_id, source, json.dumps(raw_messages), session_id, summary,
                topics or [], entities or [], status, len(raw_messages)
            )
            result = dict(row)
            result["raw_messages"] = json.loads(result["raw_messages"])
            result["topics"] = list(result.get("topics") or [])
            result["entities"] = list(result.get("entities") or [])
            return result
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[dict]:
        """Get a conversation by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, source, raw_messages, session_id, summary, topics, 
                       entities, session_status, message_count, has_decisions, has_facts, 
                       created_at, updated_at
                FROM conversations WHERE id = $1 AND user_id = $2
                """,
                conversation_id, user_id
            )
            if row:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def list_conversations(self, user_id: str, source: str = None,
                                 session_id: str = None, limit: int = 50, offset: int = 0) -> List[dict]:
        """List conversations for a user."""
        async with self.pool.acquire() as conn:
            conditions = ["user_id = $1"]
            params = [user_id]
            idx = 2
            if source:
                conditions.append(f"source = ${idx}")
                params.append(source)
                idx += 1
            if session_id:
                conditions.append(f"session_id = ${idx}")
                params.append(session_id)
                idx += 1
            params.extend([limit, offset])
            
            rows = await conn.fetch(
                f"""
                SELECT id, user_id, source, raw_messages, session_id, summary, topics, 
                       entities, session_status, message_count, has_decisions, has_facts, 
                       created_at, updated_at
                FROM conversations WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}
                """,
                *params
            )
            results = []
            for row in rows:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    async def get_conversations_by_session(self, session_id: str, user_id: str) -> List[dict]:
        """Get all conversations in a session."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, source, raw_messages, session_id, summary, topics, 
                       entities, session_status, message_count, has_decisions, has_facts, 
                       created_at, updated_at
                FROM conversations WHERE session_id = $1 AND user_id = $2
                ORDER BY created_at ASC
                """,
                session_id, user_id
            )
            results = []
            for row in rows:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    async def update_conversation(self, conversation_id: str, user_id: str,
                                  summary: str = None, topics: List[str] = None,
                                  entities: List[str] = None, embedding: List[float] = None,
                                  has_decisions: bool = None, has_facts: bool = None) -> Optional[dict]:
        """Update conversation metadata."""
        async with self.pool.acquire() as conn:
            updates = ["updated_at = NOW()"]
            params = [conversation_id, user_id]
            idx = 3
            if summary is not None:
                updates.append(f"summary = ${idx}")
                params.append(summary)
                idx += 1
            if topics is not None:
                updates.append(f"topics = ${idx}")
                params.append(topics)
                idx += 1
            if entities is not None:
                updates.append(f"entities = ${idx}")
                params.append(entities)
                idx += 1
            if embedding is not None:
                emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                updates.append(f"embedding = ${idx}::vector")
                params.append(emb_str)
                idx += 1
            if has_decisions is not None:
                updates.append(f"has_decisions = ${idx}")
                params.append(has_decisions)
                idx += 1
            if has_facts is not None:
                updates.append(f"has_facts = ${idx}")
                params.append(has_facts)
                idx += 1
            
            row = await conn.fetchrow(
                f"""
                UPDATE conversations SET {', '.join(updates)}
                WHERE id = $1 AND user_id = $2
                RETURNING id, user_id, source, raw_messages, session_id, summary, topics, 
                          entities, session_status, message_count, has_decisions, has_facts, 
                          created_at, updated_at
                """,
                *params
            )
            if row:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def link_conversation_to_session(self, conversation_id: str, user_id: str,
                                           session_id: str) -> Optional[dict]:
        """Link a conversation to a session."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE conversations SET session_id = $3, session_status = 'linked', updated_at = NOW()
                WHERE id = $1 AND user_id = $2
                RETURNING id, user_id, source, raw_messages, session_id, summary, topics, 
                          entities, session_status, message_count, has_decisions, has_facts, 
                          created_at, updated_at
                """,
                conversation_id, user_id, session_id
            )
            if row:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def unlink_conversation_from_session(self, conversation_id: str, user_id: str) -> Optional[dict]:
        """Unlink a conversation from its session."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE conversations SET session_id = NULL, session_status = 'standalone', updated_at = NOW()
                WHERE id = $1 AND user_id = $2
                RETURNING id, user_id, source, raw_messages, session_id, summary, topics, 
                          entities, session_status, message_count, has_decisions, has_facts, 
                          created_at, updated_at
                """,
                conversation_id, user_id
            )
            if row:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                return result
            return None
    
    async def count_conversations(self, user_id: str, source: str = None) -> int:
        """Count conversations for a user."""
        async with self.pool.acquire() as conn:
            if source:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM conversations WHERE user_id = $1 AND source = $2",
                    user_id, source
                )
            else:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM conversations WHERE user_id = $1",
                    user_id
                )
            return row["count"]
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id, user_id
            )
            return result == "DELETE 1"
    
    async def get_recent_conversations(self, user_id: str, limit: int = 10) -> List[dict]:
        """Get recent conversations."""
        return await self.list_conversations(user_id=user_id, limit=limit)
    
    async def search_conversations_by_embedding(self, user_id: str, embedding: List[float],
                                                limit: int = 10, threshold: float = 0.5) -> List[dict]:
        """Search conversations by embedding similarity."""
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, source, raw_messages, session_id, summary, topics, 
                       entities, session_status, message_count, has_decisions, has_facts, 
                       created_at, updated_at, 1 - (embedding <=> $1::vector) as similarity
                FROM conversations WHERE user_id = $2 AND embedding IS NOT NULL
                AND 1 - (embedding <=> $1::vector) > $3
                ORDER BY embedding <=> $1::vector LIMIT $4
                """,
                emb_str, user_id, threshold, limit
            )
            results = []
            for row in rows:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    async def search_conversations_by_topics(self, user_id: str, topics: List[str],
                                             limit: int = 10) -> List[dict]:
        """Search conversations by topics."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, source, raw_messages, session_id, summary, topics, 
                       entities, session_status, message_count, has_decisions, has_facts, 
                       created_at, updated_at
                FROM conversations WHERE user_id = $1 AND topics && $2
                ORDER BY created_at DESC LIMIT $3
                """,
                user_id, topics, limit
            )
            results = []
            for row in rows:
                result = dict(row)
                result["raw_messages"] = json.loads(result["raw_messages"])
                result["topics"] = list(result.get("topics") or [])
                result["entities"] = list(result.get("entities") or [])
                results.append(result)
            return results
    
    # =========================================================================
    # Chunk operations
    # =========================================================================
    
    async def create_chunk(self, conversation_id: str, user_id: str, content: str,
                          embedding: List[float], chunk_index: int = 0) -> dict:
        """Create a new chunk."""
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chunks (conversation_id, user_id, content, embedding, chunk_index)
                VALUES ($1, $2, $3, $4::vector, $5)
                RETURNING id, conversation_id, user_id, content, chunk_index, created_at
                """,
                conversation_id, user_id, content, emb_str, chunk_index
            )
            return dict(row)
    
    async def search_chunks(self, user_id: str, embedding: List[float],
                           limit: int = 5, threshold: float = 0.5) -> List[dict]:
        """Search chunks by embedding similarity."""
        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.id, c.content, c.created_at, c.conversation_id, conv.source,
                       conv.session_id, 1 - (c.embedding <=> $1::vector) as similarity
                FROM chunks c JOIN conversations conv ON c.conversation_id = conv.id
                WHERE c.user_id = $2 AND 1 - (c.embedding <=> $1::vector) > $3
                ORDER BY c.embedding <=> $1::vector LIMIT $4
                """,
                emb_str, user_id, threshold, limit
            )
            return [dict(row) for row in rows]
    
    # =========================================================================
    # Session Suggestion operations
    # =========================================================================
    
    async def create_session_suggestion(self, conversation_id: str,
                                        suggested_session_id: str, confidence: float) -> dict:
        """Record a session suggestion."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO session_suggestions (conversation_id, suggested_session_id, confidence)
                VALUES ($1, $2, $3)
                RETURNING id, conversation_id, suggested_session_id, confidence, accepted, created_at
                """,
                conversation_id, suggested_session_id, confidence
            )
            return dict(row)
    
    async def update_session_suggestion(self, conversation_id: str, accepted: bool,
                                        actual_session_id: str = None) -> bool:
        """Update session suggestion with user decision."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE session_suggestions SET accepted = $2, actual_session_id = $3 WHERE conversation_id = $1",
                conversation_id, accepted, actual_session_id
            )
            return "UPDATE" in result
