"""
Knowledge extraction prompts.
"""

EXTRACTION_PROMPT = """
Analyze this conversation and extract structured knowledge.

CONVERSATION:
{conversation}

Extract the following:

1. ENTITIES: People, companies, tools, technologies, projects, or concepts mentioned.
   - Include the entity name, type, and optional description
   - Types can be: Tool, Project, Company, Person, Concept, Technology

2. RELATIONSHIPS: How entities are connected.
   - Common relationship types:
     - CHOSE/DECIDED: When the user chooses or decides on something
     - BUILDS: When the user is building a project
     - USES: When a project or user uses a tool
     - WORKS_AT: When the user works at a company
     - PREFERS: When the user expresses a preference
     - RELATED_TO: General relationship between entities
   - Include properties like reason, date if mentioned

3. FACTS: Statements that might change over time.
   - Include subject, predicate, object
   - These are for temporal tracking (e.g., "User works at Google" might change)

Return valid JSON in this exact format:
{{
  "entities": [
    {{"name": "PostgreSQL", "type": "Tool", "description": "Relational database"}},
    {{"name": "E-commerce Project", "type": "Project", "description": "Online store"}}
  ],
  "relationships": [
    {{
      "source": "User",
      "target": "PostgreSQL",
      "type": "CHOSE",
      "properties": {{"reason": "ACID compliance and transaction support"}}
    }},
    {{
      "source": "E-commerce Project",
      "target": "PostgreSQL",
      "type": "USES",
      "properties": {{"purpose": "database"}}
    }}
  ],
  "facts": [
    {{
      "subject": "User",
      "predicate": "BUILDS",
      "object": "E-commerce Project",
      "valid_from": null,
      "valid_to": null
    }}
  ]
}}

Important:
- Only extract information explicitly mentioned in the conversation
- Use "User" as the subject when referring to the person in the conversation
- Be conservative - don't infer things that aren't clearly stated
- If no entities/relationships/facts are found, return empty arrays
"""
