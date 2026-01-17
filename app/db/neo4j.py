"""
Neo4j database client.
Handles Knowledge Layer: entities, relationships, facts.
"""

from neo4j import AsyncGraphDatabase
from typing import Optional, List, Any
from datetime import datetime
import uuid


class Neo4jDB:
    """Neo4j database client for Knowledge Layer."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
    
    async def connect(self):
        """Create driver connection."""
        self.driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
    
    async def disconnect(self):
        """Close driver connection."""
        if self.driver:
            await self.driver.close()
    
    # =========================================================================
    # Node operations
    # =========================================================================
    
    async def ensure_user_node(self, user_id: str):
        """Ensure a User node exists for the given user_id."""
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (u:User {user_id: $user_id})
                ON CREATE SET u.created_at = datetime()
                """,
                user_id=user_id
            )
    
    async def create_entity(
        self,
        user_id: str,
        name: str,
        entity_type: str,
        description: Optional[str] = None
    ):
        """Create or update an entity node."""
        async with self.driver.session() as session:
            # Use dynamic label based on entity_type
            query = f"""
            MERGE (e:{entity_type} {{name: $name, user_id: $user_id}})
            ON CREATE SET 
                e.created_at = datetime(),
                e.description = $description
            ON MATCH SET
                e.updated_at = datetime(),
                e.description = COALESCE($description, e.description)
            RETURN e
            """
            await session.run(
                query,
                name=name,
                user_id=user_id,
                description=description
            )
    
    async def get_entities(self, user_id: str, limit: int = 50) -> List[dict]:
        """Get all entities for a user."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e)
                WHERE e.user_id = $user_id
                AND NOT e:User
                RETURN e.name as name, labels(e)[0] as type, e.description as description
                ORDER BY e.updated_at DESC, e.created_at DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    # =========================================================================
    # Relationship operations
    # =========================================================================
    
    async def create_relationship(
        self,
        user_id: str,
        source_name: str,
        target_name: str,
        relationship_type: str,
        properties: dict = None,
        conversation_id: str = None,
        source_platform: str = None
    ):
        """Create a relationship between entities."""
        if properties is None:
            properties = {}
        
        # Add metadata
        properties["id"] = str(uuid.uuid4())
        properties["created_at"] = datetime.now().isoformat()
        if conversation_id:
            properties["conversation_id"] = conversation_id
        if source_platform:
            properties["source"] = source_platform
        
        async with self.driver.session() as session:
            # First ensure both nodes exist
            # Source is usually the User
            if source_name.lower() == "user":
                source_query = "(source:User {user_id: $user_id})"
            else:
                source_query = "(source {name: $source_name, user_id: $user_id})"
            
            query = f"""
            MATCH {source_query}
            MATCH (target {{name: $target_name, user_id: $user_id}})
            CREATE (source)-[r:{relationship_type}]->(target)
            SET r += $properties
            RETURN r
            """
            
            await session.run(
                query,
                user_id=user_id,
                source_name=source_name,
                target_name=target_name,
                properties=properties
            )
    
    async def get_decisions(self, user_id: str, limit: int = 20) -> List[dict]:
        """Get all decisions made by a user."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r:CHOSE|DECIDED]->(thing)
                RETURN 
                    r.id as id,
                    thing.name as decision,
                    thing.name as target,
                    r.reason as reason,
                    r.created_at as date,
                    r.source as source
                ORDER BY r.created_at DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    async def get_preferences(self, user_id: str, limit: int = 20) -> List[dict]:
        """Get all preferences for a user."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r:PREFERS]->(thing)
                RETURN 
                    r.id as id,
                    thing.name as target,
                    r.reason as reason,
                    r.strength as strength
                ORDER BY r.created_at DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    async def delete_relationship(self, user_id: str, relationship_id: str) -> bool:
        """Delete a relationship by ID."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r]-()
                WHERE r.id = $relationship_id
                DELETE r
                RETURN count(r) as deleted
                """,
                user_id=user_id,
                relationship_id=relationship_id
            )
            record = await result.single()
            return record["deleted"] > 0 if record else False
    
    # =========================================================================
    # Temporal fact operations
    # =========================================================================
    
    async def create_temporal_fact(
        self,
        user_id: str,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None
    ):
        """Create a temporal fact, invalidating previous facts of same type."""
        async with self.driver.session() as session:
            # First, invalidate existing facts of same type
            await session.run(
                f"""
                MATCH (s {{name: $subject, user_id: $user_id}})-[r:{predicate}]->(o)
                WHERE r.valid_to IS NULL
                SET r.valid_to = datetime()
                """,
                subject=subject,
                user_id=user_id
            )
            
            # Determine source node
            if subject.lower() == "user":
                source_match = "(s:User {user_id: $user_id})"
            else:
                source_match = "(s {name: $subject, user_id: $user_id})"
            
            # Create new fact
            query = f"""
            MATCH {source_match}
            MATCH (o {{name: $object, user_id: $user_id}})
            CREATE (s)-[r:{predicate} {{
                id: $id,
                valid_from: datetime($valid_from),
                valid_to: $valid_to
            }}]->(o)
            RETURN r
            """
            
            await session.run(
                query,
                subject=subject,
                object=obj,
                user_id=user_id,
                id=str(uuid.uuid4()),
                valid_from=valid_from or datetime.now().isoformat(),
                valid_to=valid_to
            )
    
    async def get_current_facts(self, user_id: str, limit: int = 20) -> List[dict]:
        """Get all current (valid) facts for a user."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (s)-[r]->(o)
                WHERE s.user_id = $user_id
                AND r.valid_to IS NULL
                AND NOT type(r) IN ['CHOSE', 'DECIDED', 'PREFERS']
                RETURN 
                    r.id as id,
                    CASE WHEN s:User THEN 'User' ELSE s.name END as subject,
                    type(r) as predicate,
                    o.name as object,
                    r.valid_from as since
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    # =========================================================================
    # Cleanup operations
    # =========================================================================
    
    async def delete_all_user_data(self, user_id: str) -> int:
        """Delete all data for a user from the graph."""
        async with self.driver.session() as session:
            # Delete all relationships first
            result = await session.run(
                """
                MATCH (n {user_id: $user_id})-[r]-()
                DELETE r
                RETURN count(r) as deleted_rels
                """,
                user_id=user_id
            )
            record = await result.single()
            deleted_rels = record["deleted_rels"] if record else 0
            
            # Delete all nodes (except User node)
            result = await session.run(
                """
                MATCH (n {user_id: $user_id})
                WHERE NOT n:User
                DELETE n
                RETURN count(n) as deleted_nodes
                """,
                user_id=user_id
            )
            record = await result.single()
            deleted_nodes = record["deleted_nodes"] if record else 0
            
            return deleted_rels + deleted_nodes
