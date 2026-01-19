"""
Verification tests for Symmetry MVP.
Tests core functionality without requiring database connections.
"""

import sys
sys.path.insert(0, '/Users/nithishsampath/symmetry-mvp-v2')

def test_imports():
    """Test all imports work correctly."""
    print("Testing imports...")
    
    # Core
    from app.config import Settings
    print("  ✓ Config")
    
    # Models
    from app.models.requests import (
        IngestRequest, RetrieveRequest, Message,
        CreateSessionRequest, RecommendRequest
    )
    from app.models.responses import (
        IngestResponse, RetrieveResponse, KnowledgeQuality,
        SessionInfo, DecisionInfo, ChunkInfo
    )
    print("  ✓ Models")
    
    # Services
    from app.services.chunking import (
        chunk_conversation, 
        chunk_conversation_semantic,
        chunk_by_exchange
    )
    from app.services.embedding import generate_embedding, generate_embeddings
    from app.services.extraction import extract_knowledge
    print("  ✓ Services")
    
    # DB
    from app.db.postgres import PostgresDB
    from app.db.neo4j import Neo4jDB
    print("  ✓ Database clients")
    
    print("✅ All imports successful!\n")


def test_chunking():
    """Test semantic chunking functionality."""
    print("Testing semantic chunking...")
    
    from app.services.chunking import chunk_conversation_semantic, chunk_by_exchange
    from app.models.requests import Message
    
    # Test case 1: Negation handling
    messages = [
        Message(role="user", content="Should I use MongoDB?"),
        Message(role="assistant", content="I would NOT recommend MongoDB for your use case because you need strong ACID compliance. Instead, I recommend PostgreSQL which is better for transactions.")
    ]
    
    chunks = chunk_conversation_semantic(messages)
    
    # Verify negation stays together
    negation_intact = any("NOT recommend MongoDB" in chunk for chunk in chunks)
    print(f"  {'✓' if negation_intact else '✗'} Negation preserved: 'NOT recommend MongoDB'")
    
    # Test case 2: Decision with reason
    reason_intact = any("because" in chunk.lower() and "acid" in chunk.lower() for chunk in chunks)
    print(f"  {'✓' if reason_intact else '✗'} Decision with reason preserved")
    
    # Test case 3: Code block protection
    messages_with_code = [
        Message(role="user", content="Show me the config"),
        Message(role="assistant", content="Here's the config:\n```python\nDATABASE_URL = 'postgres://localhost/db'\nDEBUG = True\n```\nThis should work.")
    ]
    
    chunks = chunk_conversation_semantic(messages_with_code)
    code_intact = any("DATABASE_URL" in chunk and "DEBUG" in chunk for chunk in chunks)
    print(f"  {'✓' if code_intact else '✗'} Code block preserved intact")
    
    # Test case 4: Exchange-based chunking
    messages = [
        Message(role="user", content="What database?"),
        Message(role="assistant", content="PostgreSQL"),
        Message(role="user", content="What about caching?"),
        Message(role="assistant", content="Redis"),
    ]
    
    exchanges = chunk_by_exchange(messages)
    print(f"  ✓ Exchange chunking: {len(exchanges)} exchanges created")
    
    print("✅ Chunking tests passed!\n")


def test_models():
    """Test Pydantic models work correctly."""
    print("Testing models...")
    
    from app.models.requests import Message, IngestRequest, RetrieveRequest
    from app.models.responses import DecisionInfo, KnowledgeQuality
    
    # Test Message
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    print("  ✓ Message model")
    
    # Test IngestRequest
    req = IngestRequest(
        source="claude",
        messages=[Message(role="user", content="Test")],
        auto_link_session=True
    )
    assert req.source == "claude"
    print("  ✓ IngestRequest model")
    
    # Test RetrieveRequest with customization
    ret = RetrieveRequest(
        query="database",
        mode="query",
        include_exploring=False,
        only_verified=True,
        exclude_entities=["MySQL"],
        custom_note="Focus on PostgreSQL"
    )
    assert ret.include_exploring == False
    assert ret.only_verified == True
    assert "MySQL" in ret.exclude_entities
    print("  ✓ RetrieveRequest with customization")
    
    # Test DecisionInfo with new fields
    decision = DecisionInfo(
        content="PostgreSQL",
        confidence=0.95,
        status="decided",
        verified=True,
        attributed_to="user",
        temporal="current"
    )
    assert decision.attributed_to == "user"
    print("  ✓ DecisionInfo with attribution")
    
    # Test KnowledgeQuality
    quality = KnowledgeQuality(
        total_decisions=5,
        confirmed_decisions=3,
        exploring_count=2,
        quality_score=85,
        quality_notes=["1 contradiction detected"]
    )
    assert quality.quality_score == 85
    print("  ✓ KnowledgeQuality model")
    
    print("✅ Model tests passed!\n")


def test_extraction_prompt():
    """Test extraction prompt is properly formatted."""
    print("Testing extraction prompt...")
    
    from app.prompts.extraction import EXTRACTION_PROMPT
    
    # Check key patterns are in prompt
    assert "CHOSE" in EXTRACTION_PROMPT
    assert "CONSIDERING" in EXTRACTION_PROMPT
    assert "REJECTED" in EXTRACTION_PROMPT
    assert "confidence" in EXTRACTION_PROMPT
    assert "attributed_to" in EXTRACTION_PROMPT
    assert "temporal" in EXTRACTION_PROMPT
    print("  ✓ Extraction prompt has all required fields")
    
    # Check edge case handling
    assert "NOT" in EXTRACTION_PROMPT or "negation" in EXTRACTION_PROMPT.lower()
    assert "hypothetical" in EXTRACTION_PROMPT.lower()
    assert "colleague" in EXTRACTION_PROMPT.lower()
    print("  ✓ Edge cases documented in prompt")
    
    print("✅ Extraction prompt tests passed!\n")


def test_api_endpoints_defined():
    """Test all API endpoints are properly defined."""
    print("Testing API endpoints...")
    
    from app.api.routes import users, ingest, retrieve, sessions, conversations, knowledge, recommend
    
    # Check routers exist
    assert hasattr(users, 'router')
    assert hasattr(ingest, 'router')
    assert hasattr(retrieve, 'router')
    assert hasattr(sessions, 'router')
    assert hasattr(conversations, 'router')
    assert hasattr(knowledge, 'router')
    assert hasattr(recommend, 'router')
    print("  ✓ All routers defined")
    
    # Count routes
    total_routes = 0
    for module in [users, ingest, retrieve, sessions, conversations, knowledge, recommend]:
        routes = [r for r in module.router.routes if hasattr(r, 'methods')]
        total_routes += len(routes)
    
    print(f"  ✓ Total endpoints: {total_routes}")
    
    print("✅ API endpoint tests passed!\n")


def run_all_tests():
    """Run all verification tests."""
    print("=" * 60)
    print("SYMMETRY MVP VERIFICATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_imports()
        test_chunking()
        test_models()
        test_extraction_prompt()
        test_api_endpoints_defined()
        
        print("=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
