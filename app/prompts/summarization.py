"""
Summarization prompts.
"""

SUMMARIZATION_PROMPT = """
Based on the user's query and their past context, provide a helpful summary.

USER'S QUERY:
{query}

RELEVANT CONVERSATIONS:
{chunks}

DECISIONS MADE:
{decisions}

CURRENT FACTS:
{facts}

RELATED ENTITIES:
{entities}

---

Provide a concise, helpful summary that:
1. Directly addresses the user's query
2. References specific decisions they've made
3. Mentions relevant context from past conversations
4. Includes when/where information came from (e.g., "In your ChatGPT conversation on Monday...")

If there's no relevant context, say so clearly and offer to help with the query directly.

Keep the summary to 2-4 sentences. Be specific and actionable.
"""
