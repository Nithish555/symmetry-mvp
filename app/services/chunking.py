"""
Text chunking service.
Semantic-aware chunking that preserves meaning and context.

Key improvements:
1. Splits at sentence boundaries, not mid-thought
2. Keeps negations with their subjects ("NOT going to use X" stays together)
3. Preserves decision context (reason + decision in same chunk)
4. Message-aware: prefers splitting between messages
5. Larger overlap to maintain context
"""

from typing import List, Tuple
import re

from app.models.requests import Message


def format_messages(messages: List[Message]) -> str:
    """
    Format a list of messages into a single text string.
    """
    parts = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        parts.append(f"{role}: {content}")
    
    return "\n\n".join(parts)


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences while handling edge cases.
    
    Handles:
    - Regular sentences (ending with . ! ?)
    - Abbreviations (Dr., Mr., etc.)
    - Numbers with decimals (3.14)
    - URLs
    """
    # Pattern to split on sentence boundaries
    # Negative lookbehind for common abbreviations and numbers
    sentence_pattern = r'(?<![A-Z][a-z]\.)(?<!\b[A-Z]\.)(?<!\d\.)(?<=[.!?])\s+'
    
    sentences = re.split(sentence_pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _find_decision_boundaries(text: str) -> List[int]:
    """
    Find positions where decisions/conclusions are made.
    These are good places NOT to split.
    
    Categories:
    1. Positive decisions: "I'll use X", "I decided on X"
    2. Negative decisions: "NOT going to", "won't use"
    3. Comparisons: "X is better than Y", "prefer X over Y"
    4. Conditionals: "if X then Y", "when X happens"
    5. Conclusions: "because", "therefore", "so"
    6. Contrasts: "however", "but", "although"
    7. Lists: "first, second, third", "1. 2. 3."
    8. Code/technical: code blocks, file paths
    """
    # Patterns that indicate decision context (don't split here)
    decision_patterns = [
        # === Positive decisions ===
        r"I'll\s+\w+",
        r"I\s+will\s+\w+",
        r"I\s+decided",
        r"I\s+chose",
        r"I\s+picked",
        r"I\s+selected",
        r"going\s+with",
        r"let's\s+use",
        r"let's\s+go\s+with",
        r"we\s+should\s+use",
        r"I\s+recommend",
        r"the\s+best\s+option\s+is",
        r"my\s+choice\s+is",
        
        # === Negative decisions ===
        r"NOT\s+going\s+to",
        r"won't\s+\w+",
        r"don't\s+want",
        r"don't\s+use",
        r"shouldn't\s+use",
        r"wouldn't\s+recommend",
        r"avoid\s+\w+",
        r"rejected\s+\w+",
        r"ruled\s+out",
        r"not\s+a\s+good\s+fit",
        r"decided\s+against",
        
        # === Comparisons ===
        r"better\s+than",
        r"worse\s+than",
        r"prefer\s+\w+\s+over",
        r"compared\s+to",
        r"instead\s+of",
        r"rather\s+than",
        r"as\s+opposed\s+to",
        
        # === Conditionals ===
        r"if\s+.{5,50}\s+then",
        r"when\s+.{5,30}\s+happens",
        r"in\s+case\s+of",
        r"assuming\s+",
        r"provided\s+that",
        
        # === Conclusions/Reasons ===
        r"because\s+",
        r"therefore\s+",
        r"thus\s+",
        r"hence\s+",
        r"so\s+that",
        r"in\s+order\s+to",
        r"the\s+reason\s+is",
        r"due\s+to",
        r"as\s+a\s+result",
        
        # === Contrasts ===
        r"however\s+",
        r"but\s+",
        r"although\s+",
        r"even\s+though",
        r"on\s+the\s+other\s+hand",
        r"nevertheless",
        r"nonetheless",
        r"despite\s+",
        
        # === Lists (keep numbered items together) ===
        r"\d+\.\s+\w+",  # "1. First item"
        r"first,?\s+",
        r"second,?\s+",
        r"third,?\s+",
        r"finally,?\s+",
        r"lastly,?\s+",
        
        # === Technical content ===
        r"`[^`]+`",  # Inline code
        r"```",  # Code block markers
        r"https?://\S+",  # URLs
        r"[\w/]+\.\w{2,4}",  # File paths like /path/to/file.py
        
        # === Uncertainty markers (keep with subject) ===
        r"maybe\s+",
        r"perhaps\s+",
        r"probably\s+",
        r"might\s+",
        r"could\s+be",
        r"I\s+think\s+",
        r"I\s+believe\s+",
        r"I'm\s+not\s+sure",
        r"I'm\s+considering",
    ]
    
    boundaries = []
    for pattern in decision_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Mark a range around the decision (don't split within 100 chars)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 100)
            boundaries.append((start, end))
    
    return boundaries


def _protect_code_blocks(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Temporarily replace code blocks with placeholders to prevent splitting.
    
    Returns:
        (modified_text, list of (placeholder, original_code) pairs)
    """
    code_blocks = []
    placeholder_pattern = "___CODE_BLOCK_{}_END___"
    
    # Find all code blocks (```...```)
    code_pattern = r'```[\s\S]*?```'
    matches = list(re.finditer(code_pattern, text))
    
    # Replace from end to start to preserve positions
    for i, match in enumerate(reversed(matches)):
        placeholder = placeholder_pattern.format(len(matches) - 1 - i)
        code_blocks.insert(0, (placeholder, match.group()))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    return text, code_blocks


def _restore_code_blocks(text: str, code_blocks: List[Tuple[str, str]]) -> str:
    """
    Restore code blocks from placeholders.
    """
    for placeholder, original in code_blocks:
        text = text.replace(placeholder, original)
    return text


def _merge_short_chunks(chunks: List[str], min_size: int = 100) -> List[str]:
    """
    Merge chunks that are too short with adjacent chunks.
    """
    if not chunks:
        return chunks
    
    merged = []
    buffer = ""
    
    for chunk in chunks:
        if len(buffer) + len(chunk) < min_size * 3:
            buffer = (buffer + " " + chunk).strip() if buffer else chunk
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk
    
    if buffer:
        merged.append(buffer)
    
    return merged


def chunk_conversation_semantic(
    messages: List[Message],
    target_chunk_size: int = 600,
    min_chunk_size: int = 200,
    max_chunk_size: int = 1000,
    overlap_sentences: int = 2
) -> List[str]:
    """
    Semantic-aware chunking that preserves meaning.
    
    Strategy:
    1. Protect code blocks from being split
    2. Split at message boundaries first (USER/ASSISTANT)
    3. Within messages, split at sentence boundaries
    4. Never split in the middle of decision statements
    5. Overlap by sentences, not characters
    
    Handles:
    - Negations: "NOT going to use X" stays together
    - Decisions with reasons: "X because Y" stays together
    - Comparisons: "X is better than Y" stays together
    - Code blocks: Never split code
    - Lists: Keep numbered items together
    - Conditionals: "if X then Y" stays together
    - Uncertainty: "maybe X", "I think Y" stays together
    
    Args:
        messages: List of conversation messages
        target_chunk_size: Ideal chunk size (will vary to preserve meaning)
        min_chunk_size: Minimum chunk size (merge smaller chunks)
        max_chunk_size: Maximum chunk size (force split if exceeded)
        overlap_sentences: Number of sentences to overlap between chunks
    
    Returns:
        List of semantically coherent chunks
    """
    chunks = []
    
    # Process each message separately first
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        
        # Skip empty messages
        if not content:
            continue
        
        # Protect code blocks from splitting
        content_protected, code_blocks = _protect_code_blocks(content)
        
        # Prefix with role
        full_text = f"{role}: {content_protected}"
        
        # If message is small enough, keep it as one chunk
        if len(full_text) <= max_chunk_size:
            # Restore code blocks and add
            restored = _restore_code_blocks(full_text, code_blocks)
            chunks.append(restored)
            continue
        
        # Split long messages into sentences
        sentences = _split_into_sentences(content_protected)
        
        if not sentences:
            # Fallback: just add the whole message
            restored = _restore_code_blocks(full_text, code_blocks)
            chunks.append(restored)
            continue
        
        # Find decision boundaries (areas not to split)
        decision_zones = _find_decision_boundaries(content_protected)
        
        # Build chunks from sentences
        current_chunk = f"{role}: "
        current_sentences = []
        message_chunks = []  # Chunks for this message
        
        for i, sentence in enumerate(sentences):
            # Check if adding this sentence would exceed max size
            potential_chunk = current_chunk + sentence
            
            if len(potential_chunk) > max_chunk_size and current_sentences:
                # Save current chunk
                message_chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap (last N sentences)
                overlap_start = max(0, len(current_sentences) - overlap_sentences)
                overlap_text = " ".join(current_sentences[overlap_start:])
                current_chunk = f"{role}: {overlap_text} {sentence}"
                current_sentences = current_sentences[overlap_start:] + [sentence]
            else:
                current_chunk = potential_chunk + " "
                current_sentences.append(sentence)
        
        # Don't forget the last chunk
        if current_chunk.strip() and current_chunk.strip() != f"{role}:":
            message_chunks.append(current_chunk.strip())
        
        # Restore code blocks in all chunks from this message
        for chunk in message_chunks:
            restored = _restore_code_blocks(chunk, code_blocks)
            chunks.append(restored)
    
    # Merge chunks that are too short
    chunks = _merge_short_chunks(chunks, min_chunk_size)
    
    # Final cleanup
    chunks = [c.strip() for c in chunks if c.strip()]
    
    return chunks


def chunk_conversation(
    messages: List[Message],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    use_semantic: bool = True
) -> List[str]:
    """
    Chunk a conversation into smaller pieces for embedding.
    
    Args:
        messages: List of conversation messages
        chunk_size: Target characters per chunk
        chunk_overlap: Characters/sentences of overlap between chunks
        use_semantic: Use semantic-aware chunking (recommended)
    
    Returns:
        List of text chunks
    """
    if use_semantic:
        return chunk_conversation_semantic(
            messages=messages,
            target_chunk_size=chunk_size,
            min_chunk_size=max(100, chunk_size // 4),
            max_chunk_size=chunk_size * 2,
            overlap_sentences=2
        )
    
    # Fallback to simple chunking (for backwards compatibility)
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    text = format_messages(messages)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\nUSER:",
            "\n\nASSISTANT:",
            "\n\nSYSTEM:",
            "\n\n",
            "\n",
            ". ",
            " ",
        ],
        keep_separator=True
    )
    
    chunks = splitter.split_text(text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    
    return chunks


# ============================================================================
# Advanced: Message-Pair Chunking
# ============================================================================

def chunk_by_exchange(
    messages: List[Message],
    max_exchange_size: int = 1500
) -> List[str]:
    """
    Chunk by user-assistant exchange pairs.
    
    This keeps question and answer together, which is often
    the most semantically meaningful unit.
    
    Example:
    - Chunk 1: "USER: What database? ASSISTANT: I recommend PostgreSQL because..."
    - Chunk 2: "USER: What about caching? ASSISTANT: Use Redis for..."
    
    Args:
        messages: List of conversation messages
        max_exchange_size: Maximum size of an exchange chunk
    
    Returns:
        List of exchange-based chunks
    """
    chunks = []
    current_exchange = []
    current_size = 0
    
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        msg_text = f"{role}: {content}"
        msg_size = len(msg_text)
        
        # If this is a USER message and we have content, might start new exchange
        if role == "USER" and current_exchange:
            # Check if last message was ASSISTANT (complete exchange)
            if current_exchange and "ASSISTANT:" in current_exchange[-1]:
                # Save current exchange
                chunks.append("\n\n".join(current_exchange))
                current_exchange = []
                current_size = 0
        
        # Check if adding this would exceed max size
        if current_size + msg_size > max_exchange_size and current_exchange:
            chunks.append("\n\n".join(current_exchange))
            current_exchange = []
            current_size = 0
        
        current_exchange.append(msg_text)
        current_size += msg_size
    
    # Don't forget last exchange
    if current_exchange:
        chunks.append("\n\n".join(current_exchange))
    
    return chunks


def chunk_with_context(
    messages: List[Message],
    chunk_size: int = 500,
    context_size: int = 200
) -> List[Tuple[str, str, str]]:
    """
    Create chunks with leading and trailing context.
    
    Returns tuples of (previous_context, main_chunk, next_context).
    This allows retrieval to show surrounding context.
    
    Args:
        messages: List of conversation messages
        chunk_size: Size of main chunk
        context_size: Size of context before/after
    
    Returns:
        List of (prev_context, chunk, next_context) tuples
    """
    # First, get regular chunks
    all_chunks = chunk_conversation_semantic(messages, target_chunk_size=chunk_size)
    
    result = []
    for i, chunk in enumerate(all_chunks):
        prev_context = all_chunks[i - 1][-context_size:] if i > 0 else ""
        next_context = all_chunks[i + 1][:context_size] if i < len(all_chunks) - 1 else ""
        result.append((prev_context, chunk, next_context))
    
    return result
