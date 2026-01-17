// Symmetry MVP - Neo4j Schema Setup
// Run these commands in Neo4j Browser or Aura Console

// Create constraints for unique identification

// User constraint
CREATE CONSTRAINT user_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

// Tool constraint (per user)
CREATE CONSTRAINT tool_unique IF NOT EXISTS
FOR (t:Tool) REQUIRE (t.name, t.user_id) IS UNIQUE;

// Project constraint (per user)
CREATE CONSTRAINT project_unique IF NOT EXISTS
FOR (p:Project) REQUIRE (p.name, p.user_id) IS UNIQUE;

// Company constraint (per user)
CREATE CONSTRAINT company_unique IF NOT EXISTS
FOR (c:Company) REQUIRE (c.name, c.user_id) IS UNIQUE;

// Concept constraint (per user)
CREATE CONSTRAINT concept_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE (c.name, c.user_id) IS UNIQUE;

// Technology constraint (per user)
CREATE CONSTRAINT technology_unique IF NOT EXISTS
FOR (t:Technology) REQUIRE (t.name, t.user_id) IS UNIQUE;

// Create indexes for faster lookups

// Index on user_id for all node types
CREATE INDEX user_id_index IF NOT EXISTS
FOR (n:User) ON (n.user_id);

// Index for looking up entities by user
CREATE INDEX tool_user_index IF NOT EXISTS
FOR (t:Tool) ON (t.user_id);

CREATE INDEX project_user_index IF NOT EXISTS
FOR (p:Project) ON (p.user_id);

CREATE INDEX company_user_index IF NOT EXISTS
FOR (c:Company) ON (c.user_id);

// Index on relationship properties
// Note: Neo4j 5.x+ supports relationship property indexes

// Verify setup
CALL db.constraints();
CALL db.indexes();
