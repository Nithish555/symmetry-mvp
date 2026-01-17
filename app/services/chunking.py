"""
Text chunking service.
Splits conversations into searchable chunks.
"""

from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.requests import Message


def format_messages(messages: List[Message]) -> str:
    """
    Format a list of messages into a single text string.
    
    Example output:
    "USER: What database should I use?
    
    ASSISTANT: I recommend PostgreSQL..."
    """
    parts = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        parts.append(f"{role}: {content}")
    
    return "\n\n".join(parts)


def chunk_conversation(
    messages: List[Message],
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[str]:
    """
    Chunk a conversation into smaller pieces for embedding.
    
    Args:
        messages: List of conversation messages
        chunk_size: Maximum characters per chunk
        chunk_overlap: Characters of overlap between chunks
    
    Returns:
        List of text chunks
    """
    # Format messages into single text
    text = format_messages(messages)
    
    # Create splitter with conversation-aware separators
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\nUSER:",      # Best: split between user messages
            "\n\nASSISTANT:", # Good: split between assistant messages
            "\n\nSYSTEM:",    # Good: split at system messages
            "\n\n",           # OK: split at double newline
            "\n",             # Fallback: split at newline
            ". ",             # Fallback: split at sentence
            " ",              # Last resort: split at space
        ],
        keep_separator=True
    )
    
    # Split text into chunks
    chunks = splitter.split_text(text)
    
    # Clean up chunks (remove leading/trailing whitespace)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    
    return chunks
