#!/usr/bin/env python3
"""
UserPromptSubmit hook - triggers documentation reading when user says "read the docs".
Also suggests relevant docs based on keywords in the user's message.
"""
import json
import sys

# Keyword to document mapping for smart doc suggestions
DOC_KEYWORDS = {
    "elasticsearch": ["entities/README.md", "data_models/README.md"],
    "index template": ["entities/README.md", "data_models/README.md"],
    "mapping": ["entities/README.md", "pauwels_*.json"],
    "api": ["entities/open_api/", "pauwels_data_api_openapi.json"],
    "openapi": ["entities/open_api/", "pauwels_data_api_openapi.json"],
    "diagram": ["diagrams/INDEX.md"],
    "architecture": ["diagrams/INDEX.md", "docs/TECHNICAL_OVERVIEW.md"],
    "integration": ["docs/integrations/README.md"],
    "bullhorn": ["bullhorn_docs_split/Index.md"],
    "clerk": ["Clerk/Index.md"],
    "auth": ["Clerk/Index.md"],
    "exa": ["Exa-AI/Websets_cleaned/Index.md"],
    "websets": ["Exa-AI/Websets_cleaned/Index.md"],
    "logfire": ["Pydantic/Logfire_cleaned/Index.md"],
    "pydantic": ["Pydantic/PydanticAI_cleaned/Index.md"],
    "pydanticai": ["Pydantic/PydanticAI_cleaned/Index.md"],
    "agent": ["Pydantic/PydanticAI_cleaned/Index.md"],
    "hook": ["prompts/docs/concepts/hooks.md"],
    "command": ["prompts/docs/concepts/commands.md"],
    "skill": ["prompts/docs/concepts/skills.md"],
    "toolkit": ["prompts/README.md", "prompts/docs/index.md"],
    "person": ["entities/example_data/person.json", "pauwels_person.json"],
    "company": ["entities/example_data/company.json", "pauwels_company.json"],
    "vacancy": ["entities/example_data/vacancy.json", "pauwels_vacancy.json"],
    "match": ["entities/example_data/match.json", "pauwels_match.json"],
    "placement": ["entities/example_data/placement.json", "pauwels_placement.json"],
    "time": ["entities/example_data/time.json", "pauwels_time.json"],
    "appointment": ["entities/example_data/appointment.json", "pauwels_appointment.json"],
    "note": ["entities/example_data/note.json", "pauwels_note.json"],
}


def suggest_relevant_docs(message: str) -> list[str]:
    """Return list of docs relevant to the user's message."""
    suggestions = []
    message_lower = message.lower()
    for keyword, docs in DOC_KEYWORDS.items():
        if keyword in message_lower:
            suggestions.extend(docs)
    # Deduplicate and limit to 3
    return list(dict.fromkeys(suggestions))[:3]


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    message = input_data.get("message", "").lower()

    # Check for keyword-based doc suggestions (always runs)
    suggested_docs = suggest_relevant_docs(message)

    # Only show full reminder when user explicitly requests doc reading
    if "read the docs" in message:
        reminder = """Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched: 'read the docs')

Before starting this task, you MUST:

1. Read docs/index.md to understand the documentation structure
2. Read docs/TECHNICAL_OVERVIEW.md for mid-level system understanding
3. Use the docs-navigator skill pattern to identify relevant docs
4. Match your task keywords to the index keywords
5. Read ONLY the 1-3 most relevant docs (not all)
6. Apply the patterns and conventions documented there

Do NOT skip this step. Do NOT read all docs. Read smart, not everything."""
        print(reminder)
    elif suggested_docs:
        # Suggest specific docs based on keywords detected
        docs_list = "\n  - ".join(suggested_docs)
        hint = f"""Consider using the Skill tool for this task. Relevant skills:
  - /docs-navigator (matched: 'read the docs')

Based on your task, these docs may be relevant:
  - {docs_list}

Read these BEFORE starting work to understand existing patterns."""
        print(hint)

    sys.exit(0)


if __name__ == "__main__":
    main()
