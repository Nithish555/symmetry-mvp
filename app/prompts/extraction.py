"""
Knowledge extraction prompts.
Production-level extraction with comprehensive edge case handling.
"""

EXTRACTION_PROMPT = """
You are a precise knowledge extraction system. Extract ONLY what is explicitly stated.
Your goal is to capture the user's ACTUAL decisions, not assumptions.

CONVERSATION:
{conversation}

═══════════════════════════════════════════════════════════════════════════════
EXTRACTION RULES (CRITICAL - Follow these exactly)
═══════════════════════════════════════════════════════════════════════════════

## RULE 1: Decision Status Classification

| User Says | Status | Type | Confidence |
|-----------|--------|------|------------|
| "I'll use X", "I decided on X", "Going with X" | decided | CHOSE | 0.85-1.0 |
| "I think X", "Leaning toward X", "X seems good" | exploring | CONSIDERING | 0.5-0.7 |
| "Maybe X", "What about X?", "Could use X" | exploring | CONSIDERING | 0.3-0.5 |
| "I won't use X", "Not going with X", "Ruled out X" | rejected | REJECTED | 0.8-1.0 |
| "I prefer X over Y" (but not decided) | exploring | PREFERS | 0.6-0.8 |

## RULE 2: Things that are NOT User Decisions (DO NOT extract as CHOSE)

❌ Hypotheticals: "If we used X...", "Assuming we go with X..."
   → Extract as CONSIDERING with confidence 0.3, note: "hypothetical"

❌ Comparisons: "X is better than Y", "X has more features"
   → Do NOT extract as user's choice, just note the comparison

❌ Questions: "Should I use X?", "What do you think about X?"
   → Extract as CONSIDERING with confidence 0.2, note: "asking about"

❌ Others' opinions: "My colleague suggested X", "The article recommended X"
   → Extract with attributed_to field, NOT as user's decision

❌ Past usage: "I used to use X", "Last year we had X"
   → Extract with temporal: "past", NOT as current

❌ Conditional: "If budget allows, we'll use X"
   → Extract as CONSIDERING with confidence 0.4, note the condition

❌ Examples: "For example, X could...", "Like X does..."
   → Do NOT extract as decision

## RULE 3: Negation Detection (CRITICAL)

When you see negation words, extract as REJECTED:
- "NOT", "won't", "don't", "can't", "shouldn't", "wouldn't"
- "decided against", "ruled out", "eliminated", "rejected"
- "not going to", "not planning to", "avoiding"

Example: "I'm NOT going to use MongoDB" → REJECTED (not CHOSE!)

## RULE 4: Confidence Scoring

| Confidence | Meaning | Example Phrases |
|------------|---------|-----------------|
| 0.95-1.0 | Definitive decision | "I will definitely", "Final decision is", "We're going with" |
| 0.8-0.9 | Strong decision | "I'll use", "I decided", "Going to use" |
| 0.6-0.7 | Leaning toward | "I think", "Probably", "Most likely" |
| 0.4-0.5 | Considering | "Maybe", "Could", "Might", "Possibly" |
| 0.2-0.3 | Just exploring | "What about", "Have you heard of", "Looking into" |
| 0.1 | Mentioned only | Just named without any context |

## RULE 5: Source Attribution

Always note WHO said something:
- user: The person in the conversation
- colleague: Someone the user mentioned
- article/docs: External source
- ai_suggestion: The AI assistant suggested it

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return valid JSON:
{{
  "entities": [
    {{
      "name": "PostgreSQL",
      "type": "Tool",
      "description": "Relational database",
      "first_mentioned": "context of first mention"
    }}
  ],
  "relationships": [
    {{
      "source": "User",
      "target": "PostgreSQL",
      "type": "CHOSE",
      "status": "decided",
      "confidence": 0.9,
      "attributed_to": "user",
      "temporal": "current",
      "properties": {{
        "reason": "ACID compliance",
        "condition": null,
        "note": null
      }}
    }},
    {{
      "source": "User",
      "target": "MongoDB",
      "type": "CONSIDERING",
      "status": "exploring",
      "confidence": 0.3,
      "attributed_to": "colleague",
      "temporal": "current",
      "properties": {{
        "reason": "Colleague suggested it",
        "condition": null,
        "note": "Not user's own preference"
      }}
    }},
    {{
      "source": "User",
      "target": "MySQL",
      "type": "REJECTED",
      "status": "rejected",
      "confidence": 0.85,
      "attributed_to": "user",
      "temporal": "current",
      "properties": {{
        "reason": "Lacks needed features",
        "condition": null,
        "note": null
      }}
    }},
    {{
      "source": "User",
      "target": "DynamoDB",
      "type": "USED",
      "status": "past",
      "confidence": 0.9,
      "attributed_to": "user",
      "temporal": "past",
      "properties": {{
        "reason": null,
        "condition": null,
        "note": "Previous project, not current"
      }}
    }}
  ],
  "facts": [
    {{
      "subject": "User",
      "predicate": "WORKS_AT",
      "object": "TechCorp",
      "confidence": 1.0,
      "temporal": "current"
    }},
    {{
      "subject": "User",
      "predicate": "WORKED_AT",
      "object": "StartupXYZ",
      "confidence": 0.9,
      "temporal": "past"
    }}
  ],
  "warnings": [
    {{
      "type": "ambiguous",
      "message": "User mentioned both PostgreSQL and MongoDB positively - unclear which is chosen",
      "entities": ["PostgreSQL", "MongoDB"]
    }}
  ]
}}

═══════════════════════════════════════════════════════════════════════════════
FINAL CHECKLIST (Apply before returning)
═══════════════════════════════════════════════════════════════════════════════

✓ Did I mark hypotheticals as CONSIDERING, not CHOSE?
✓ Did I catch all negations and mark them as REJECTED?
✓ Did I attribute suggestions from others correctly?
✓ Did I mark past usage as temporal: "past"?
✓ Did I give low confidence to questions and explorations?
✓ Did I only use CHOSE for explicit, definitive decisions?
✓ Did I add warnings for ambiguous situations?

If no clear entities/relationships/facts found, return empty arrays.
When in doubt, use LOWER confidence and CONSIDERING status.
"""


# Prompt for re-analyzing existing knowledge (for corrections)
REANALYSIS_PROMPT = """
Review this extracted knowledge and the original conversation.
Identify any errors or improvements needed.

ORIGINAL CONVERSATION:
{conversation}

EXTRACTED KNOWLEDGE:
{knowledge}

Check for these common errors:
1. CHOSE when user was just exploring
2. Missing REJECTED for negations
3. Missing source attribution
4. Past usage marked as current
5. Hypotheticals marked as decisions
6. Questions marked as preferences

Return corrections in this format:
{{
  "corrections": [
    {{
      "relationship_id": "...",
      "issue": "Marked as CHOSE but user was just asking",
      "suggested_type": "CONSIDERING",
      "suggested_confidence": 0.3,
      "suggested_status": "exploring"
    }}
  ],
  "missing": [
    {{
      "description": "User rejected MySQL but not captured",
      "suggested_relationship": {{...}}
    }}
  ]
}}
"""
