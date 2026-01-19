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
    
    async def find_related_entities(
        self, 
        user_id: str, 
        search_terms: List[str], 
        max_hops: int = 2,
        limit: int = 10
    ) -> List[str]:
        """
        Find entities related to the given search terms by traversing the knowledge graph.
        
        This enables query expansion for better recall:
        - User searches "caching"
        - Graph finds: caching → Redis → session storage
        - Returns: ["Redis", "session storage", "TTL", ...]
        
        Args:
            user_id: User's ID
            search_terms: Keywords from the user's query
            max_hops: Maximum relationship hops to traverse (1-3)
            limit: Maximum related entities to return
            
        Returns:
            List of related entity names for query expansion
        """
        if not self.driver:
            return []
        
        async with self.driver.session() as session:
            # Build a case-insensitive search for any of the terms
            # Look for entities whose name contains any search term
            result = await session.run(
                """
                // Find entities matching any search term (case-insensitive)
                UNWIND $search_terms AS term
                MATCH (start)
                WHERE start.user_id = $user_id
                AND toLower(start.name) CONTAINS toLower(term)
                AND NOT start:User
                
                // Traverse 1-2 hops to find related entities
                MATCH path = (start)-[*1..2]-(related)
                WHERE related.user_id = $user_id
                AND NOT related:User
                AND related <> start
                
                // Return unique related entity names with relevance score
                WITH related, 
                     length(path) AS distance,
                     COUNT(*) AS connection_count
                RETURN DISTINCT related.name AS name,
                       related.type AS type,
                       distance,
                       connection_count
                ORDER BY distance ASC, connection_count DESC
                LIMIT $limit
                """,
                user_id=user_id,
                search_terms=search_terms,
                limit=limit
            )
            records = await result.data()
            
            # Extract just the entity names
            return [r["name"] for r in records if r.get("name")]
    
    async def get_entity_context(
        self,
        user_id: str,
        entity_name: str
    ) -> dict:
        """
        Get full context about an entity including all its relationships.
        
        Useful for understanding what the user knows about a specific topic.
        
        Returns:
            {
                "entity": {"name": "Redis", "type": "Tool"},
                "relationships": [
                    {"type": "USED_FOR", "target": "Caching", "direction": "outgoing"},
                    {"type": "CHOSE", "source": "User", "direction": "incoming"}
                ]
            }
        """
        if not self.driver:
            return {"entity": None, "relationships": []}
        
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e {name: $entity_name, user_id: $user_id})
                WHERE NOT e:User
                OPTIONAL MATCH (e)-[r_out]->(target)
                WHERE target.user_id = $user_id
                OPTIONAL MATCH (source)-[r_in]->(e)
                WHERE source.user_id = $user_id
                
                WITH e,
                     COLLECT(DISTINCT {type: type(r_out), target: target.name, direction: 'outgoing'}) AS outgoing,
                     COLLECT(DISTINCT {type: type(r_in), source: source.name, direction: 'incoming'}) AS incoming
                
                RETURN e.name AS name,
                       labels(e)[0] AS type,
                       e.description AS description,
                       outgoing + incoming AS relationships
                """,
                entity_name=entity_name,
                user_id=user_id
            )
            record = await result.single()
            
            if not record:
                return {"entity": None, "relationships": []}
            
            return {
                "entity": {
                    "name": record["name"],
                    "type": record["type"],
                    "description": record["description"]
                },
                "relationships": [
                    r for r in record["relationships"] 
                    if r.get("target") or r.get("source")  # Filter out empty relationships
                ]
            }
    
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
        source_platform: str = None,
        confidence: float = 1.0,
        status: str = "decided",
        attributed_to: str = "user",
        temporal: str = "current"
    ):
        """
        Create a relationship between entities.
        
        Args:
            confidence: 0.0-1.0 indicating certainty of this relationship
            status: "decided", "exploring", "rejected"
            attributed_to: "user", "colleague", "article", "ai_suggestion"
            temporal: "current", "past", "future"
        """
        if properties is None:
            properties = {}
        
        # Add metadata
        properties["id"] = str(uuid.uuid4())
        properties["created_at"] = datetime.now().isoformat()
        properties["confidence"] = confidence
        properties["status"] = status
        properties["verified"] = False  # User hasn't verified this yet
        properties["attributed_to"] = attributed_to  # Who said this
        properties["temporal"] = temporal  # Is this current or past?
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
    
    async def get_decisions(
        self, 
        user_id: str, 
        limit: int = 20, 
        include_low_confidence: bool = False,
        include_past: bool = False,
        include_others_suggestions: bool = False
    ) -> List[dict]:
        """
        Get all decisions made by a user.
        
        By default, only returns:
        - High-confidence decisions (>= 0.7)
        - Current decisions (not past)
        - User's own decisions (not colleague suggestions)
        
        Args:
            include_low_confidence: Include decisions with confidence < 0.7
            include_past: Include past decisions (temporal = 'past')
            include_others_suggestions: Include decisions attributed to others
        """
        # Build filters
        filters = ["(r.status IS NULL OR r.status = 'decided')"]
        
        if not include_low_confidence:
            filters.append("(r.confidence IS NULL OR r.confidence >= 0.7)")
        
        if not include_past:
            filters.append("(r.temporal IS NULL OR r.temporal = 'current')")
        
        if not include_others_suggestions:
            filters.append("(r.attributed_to IS NULL OR r.attributed_to = 'user')")
        
        filter_clause = " AND ".join(filters)
        
        async with self.driver.session() as session:
            result = await session.run(
                f"""
                MATCH (u:User {{user_id: $user_id}})-[r:CHOSE|DECIDED]->(thing)
                WHERE {filter_clause}
                RETURN 
                    r.id as id,
                    thing.name as decision,
                    thing.name as target,
                    r.reason as reason,
                    r.confidence as confidence,
                    r.status as status,
                    r.verified as verified,
                    r.attributed_to as attributed_to,
                    r.temporal as temporal,
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
    
    async def get_exploring(self, user_id: str, limit: int = 20) -> List[dict]:
        """
        Get items the user is exploring/considering (not decided yet).
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r:CONSIDERING|PREFERS]->(thing)
                WHERE r.status = 'exploring' OR r.status IS NULL
                RETURN 
                    r.id as id,
                    thing.name as target,
                    type(r) as relationship_type,
                    r.reason as reason,
                    r.confidence as confidence,
                    r.status as status,
                    r.attributed_to as attributed_to,
                    r.created_at as date,
                    r.source as source
                ORDER BY r.confidence DESC, r.created_at DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    async def get_rejected(self, user_id: str, limit: int = 20) -> List[dict]:
        """
        Get items the user has explicitly rejected.
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r:REJECTED]->(thing)
                RETURN 
                    r.id as id,
                    thing.name as target,
                    r.reason as reason,
                    r.confidence as confidence,
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
    
    async def get_all_knowledge_categorized(self, user_id: str) -> dict:
        """
        Get all knowledge categorized by status.
        Returns a clear picture of what user decided, is exploring, and rejected.
        """
        decisions = await self.get_decisions(user_id, include_low_confidence=True)
        exploring = await self.get_exploring(user_id)
        rejected = await self.get_rejected(user_id)
        
        return {
            "decided": decisions,
            "exploring": exploring,
            "rejected": rejected,
            "summary": {
                "total_decisions": len(decisions),
                "high_confidence": sum(1 for d in decisions if (d.get("confidence") or 1.0) >= 0.8),
                "low_confidence": sum(1 for d in decisions if (d.get("confidence") or 1.0) < 0.8),
                "exploring_count": len(exploring),
                "rejected_count": len(rejected)
            }
        }
    
    async def detect_contradictions(self, user_id: str) -> List[dict]:
        """
        Detect contradictory decisions.
        Returns pairs of decisions that might conflict.
        
        Examples:
        - User CHOSE PostgreSQL, then later CHOSE MySQL (same category)
        - User REJECTED X, then later CHOSE X
        """
        async with self.driver.session() as session:
            # Find cases where user chose something, then chose something else in same category
            result = await session.run(
                """
                // Find decisions on same type of entity (potential conflicts)
                MATCH (u:User {user_id: $user_id})-[r1:CHOSE|DECIDED]->(t1)
                MATCH (u)-[r2:CHOSE|DECIDED]->(t2)
                WHERE t1 <> t2
                AND labels(t1) = labels(t2)
                AND r1.created_at < r2.created_at
                AND (r1.status IS NULL OR r1.status = 'decided')
                AND (r2.status IS NULL OR r2.status = 'decided')
                RETURN 
                    r1.id as old_id,
                    t1.name as old_decision,
                    r1.created_at as old_date,
                    r1.reason as old_reason,
                    r2.id as new_id,
                    t2.name as new_decision,
                    r2.created_at as new_date,
                    r2.reason as new_reason,
                    labels(t1)[0] as category,
                    'changed_decision' as conflict_type
                ORDER BY r2.created_at DESC
                LIMIT 10
                """,
                user_id=user_id
            )
            conflicts = await result.data()
            
            # Also find REJECTED then CHOSE conflicts
            result2 = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r1:REJECTED]->(t)
                MATCH (u)-[r2:CHOSE|DECIDED]->(t)
                WHERE r1.created_at < r2.created_at
                RETURN 
                    r1.id as old_id,
                    t.name as target,
                    r1.created_at as rejected_date,
                    r2.id as new_id,
                    r2.created_at as chose_date,
                    'rejected_then_chose' as conflict_type
                ORDER BY r2.created_at DESC
                LIMIT 10
                """,
                user_id=user_id
            )
            rejected_conflicts = await result2.data()
            
            return conflicts + rejected_conflicts
    
    async def get_decision_history(self, user_id: str, entity_name: str) -> List[dict]:
        """
        Get the history of decisions/considerations for a specific entity.
        Useful for understanding how user's opinion changed over time.
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r]->(t {name: $entity_name})
                WHERE type(r) IN ['CHOSE', 'DECIDED', 'CONSIDERING', 'REJECTED', 'PREFERS']
                RETURN 
                    r.id as id,
                    type(r) as action,
                    r.status as status,
                    r.confidence as confidence,
                    r.reason as reason,
                    r.source as source,
                    r.created_at as date
                ORDER BY r.created_at ASC
                """,
                user_id=user_id,
                entity_name=entity_name
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
    
    async def update_relationship(
        self, 
        user_id: str, 
        relationship_id: str,
        status: str = None,
        confidence: float = None,
        verified: bool = None,
        reason: str = None
    ) -> Optional[dict]:
        """
        Update a relationship's properties.
        Used for correcting extraction errors or verifying knowledge.
        """
        updates = []
        params = {"user_id": user_id, "relationship_id": relationship_id}
        
        if status is not None:
            updates.append("r.status = $status")
            params["status"] = status
        if confidence is not None:
            updates.append("r.confidence = $confidence")
            params["confidence"] = confidence
        if verified is not None:
            updates.append("r.verified = $verified")
            params["verified"] = verified
        if reason is not None:
            updates.append("r.reason = $reason")
            params["reason"] = reason
        
        if not updates:
            return None
        
        updates.append("r.updated_at = datetime()")
        
        async with self.driver.session() as session:
            result = await session.run(
                f"""
                MATCH ()-[r]->()
                WHERE r.id = $relationship_id
                SET {', '.join(updates)}
                RETURN r.id as id, type(r) as type, r.status as status, 
                       r.confidence as confidence, r.verified as verified,
                       r.reason as reason
                """,
                **params
            )
            record = await result.single()
            return dict(record) if record else None
    
    async def verify_relationship(self, user_id: str, relationship_id: str, is_correct: bool) -> Optional[dict]:
        """
        Mark a relationship as verified by the user.
        
        If is_correct=True:
          - Marks as verified
          - Boosts confidence to at least 0.9
          - Changes status to "decided" (user confirmed it)
        
        If is_correct=False:
          - Marks as incorrect for review/deletion
        """
        async with self.driver.session() as session:
            if is_correct:
                # User confirmed this is correct:
                # 1. Mark as verified
                # 2. Boost confidence (min 0.9)
                # 3. Change status to "decided" since user confirmed
                result = await session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.id = $relationship_id
                    SET r.verified = true, 
                        r.verified_at = datetime(),
                        r.confidence = CASE 
                            WHEN r.confidence IS NULL OR r.confidence < 0.9 THEN 0.95 
                            ELSE r.confidence 
                        END,
                        r.status = 'decided'
                    RETURN r.id as id, type(r) as type, r.verified as verified, 
                           r.confidence as confidence, r.status as status
                    """,
                    relationship_id=relationship_id
                )
            else:
                # Mark as incorrect - user can then delete or correct
                result = await session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.id = $relationship_id
                    SET r.verified = false, 
                        r.marked_incorrect = true, 
                        r.marked_at = datetime(),
                        r.confidence = 0.1
                    RETURN r.id as id, type(r) as type, r.marked_incorrect as marked_incorrect
                    """,
                    relationship_id=relationship_id
                )
            record = await result.single()
            return dict(record) if record else None
    
    async def get_unverified_knowledge(self, user_id: str, limit: int = 20) -> List[dict]:
        """
        Get knowledge that hasn't been verified by the user.
        Prioritizes low-confidence and recent extractions.
        """
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (u:User {user_id: $user_id})-[r]->(target)
                WHERE r.verified IS NULL OR r.verified = false
                AND (r.marked_incorrect IS NULL OR r.marked_incorrect = false)
                RETURN 
                    r.id as id,
                    type(r) as relationship_type,
                    target.name as target,
                    r.status as status,
                    r.confidence as confidence,
                    r.reason as reason,
                    r.source as source,
                    r.created_at as created_at
                ORDER BY r.confidence ASC, r.created_at DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit
            )
            records = await result.data()
            return records
    
    async def get_relationship_by_id(self, relationship_id: str) -> Optional[dict]:
        """Get a specific relationship by ID."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (source)-[r]->(target)
                WHERE r.id = $relationship_id
                RETURN 
                    r.id as id,
                    type(r) as relationship_type,
                    CASE WHEN source:User THEN 'User' ELSE source.name END as source,
                    target.name as target,
                    r.status as status,
                    r.confidence as confidence,
                    r.reason as reason,
                    r.verified as verified,
                    r.source as platform,
                    r.created_at as created_at
                """,
                relationship_id=relationship_id
            )
            record = await result.single()
            return dict(record) if record else None
    
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
