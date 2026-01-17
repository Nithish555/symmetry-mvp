"""
Tests for the chunking service.
"""

import pytest
from app.services.chunking import chunk_conversation, format_messages
from app.models.requests import Message


def test_format_messages():
    """Test message formatting."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!")
    ]
    
    result = format_messages(messages)
    
    assert "USER: Hello" in result
    assert "ASSISTANT: Hi there!" in result


def test_format_messages_preserves_order():
    """Test that message order is preserved."""
    messages = [
        Message(role="user", content="First"),
        Message(role="assistant", content="Second"),
        Message(role="user", content="Third")
    ]
    
    result = format_messages(messages)
    lines = result.split("\n\n")
    
    assert "First" in lines[0]
    assert "Second" in lines[1]
    assert "Third" in lines[2]


def test_chunk_conversation():
    """Test conversation chunking."""
    messages = [
        Message(role="user", content="What database should I use for my project?"),
        Message(role="assistant", content="I recommend PostgreSQL because it offers ACID compliance.")
    ]
    
    chunks = chunk_conversation(messages, chunk_size=100, chunk_overlap=20)
    
    assert len(chunks) > 0
    assert all(isinstance(c, str) for c in chunks)


def test_chunk_conversation_respects_size():
    """Test that chunks respect size limits."""
    messages = [
        Message(role="user", content="A" * 200),
        Message(role="assistant", content="B" * 200)
    ]
    
    chunks = chunk_conversation(messages, chunk_size=100, chunk_overlap=10)
    
    # Most chunks should be around the chunk_size
    for chunk in chunks:
        # Allow some flexibility for overlap and separators
        assert len(chunk) <= 150  # chunk_size + some buffer


def test_chunk_empty_conversation():
    """Test chunking empty conversation."""
    chunks = chunk_conversation([], chunk_size=100, chunk_overlap=20)
    assert chunks == []


def test_chunk_single_short_message():
    """Test chunking a single short message."""
    messages = [
        Message(role="user", content="Hello")
    ]
    
    chunks = chunk_conversation(messages, chunk_size=500, chunk_overlap=50)
    
    assert len(chunks) == 1
    assert "USER: Hello" in chunks[0]
