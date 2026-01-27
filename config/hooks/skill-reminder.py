#!/usr/bin/env python3
"""
UserPromptSubmit hook that suggests relevant skills based on prompt keywords.
Dynamically reads skill triggers from SKILL.md files.
"""
import json
import re
import sys
from pathlib import Path


def load_skills() -> dict[str, list[str]]:
    """Load skill names and their trigger keywords from SKILL.md files."""
    skills_dir = Path.home() / ".claude" / "skills"
    skills = {}

    if not skills_dir.exists():
        return skills

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        skill_name = skill_dir.name
        triggers = extract_triggers(skill_md)
        if triggers:
            skills[skill_name] = triggers

    return skills


def extract_triggers(skill_md: Path) -> list[str]:
    """Extract trigger keywords from SKILL.md description field."""
    content = skill_md.read_text()

    # Look for description in frontmatter or first paragraph
    # Pattern 1: YAML frontmatter description
    match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE)
    if match:
        desc = match.group(1).strip().strip('"').strip("'")
        # Extract quoted trigger words or significant terms
        triggers = re.findall(r'"([^"]+)"', desc)
        if triggers:
            return [t.lower() for t in triggers]

    # Pattern 2: Look for "Triggers on:" or similar
    match = re.search(r"[Tt]riggers?\s+on[:\s]+(.+?)(?:\n|$)", content)
    if match:
        trigger_text = match.group(1)
        triggers = re.findall(r'"([^"]+)"', trigger_text)
        if triggers:
            return [t.lower() for t in triggers]

    # Pattern 3: Extract from "Use when" or "Use this when" patterns
    match = re.search(r"[Uu]se (?:this )?when[:\s]+(.+?)(?:\.|$)", content)
    if match:
        # Extract key terms from the description
        text = match.group(1).lower()
        keywords = []
        # Common important terms
        for term in [
            "async",
            "frontend",
            "design",
            "testing",
            "playwright",
            "next.js",
            "tanstack",
            "prompt",
            "ux",
            "api",
            "websocket",
            "dashboard",
            "table",
            "form",
            "component",
        ]:
            if term in text:
                keywords.append(term)
        return keywords

    return []


def find_matching_skills(
    prompt: str, skills: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """Find skills whose triggers match the prompt."""
    prompt_lower = prompt.lower()
    matches = []

    for skill_name, triggers in skills.items():
        for trigger in triggers:
            if trigger in prompt_lower:
                matches.append((skill_name, trigger))
                break  # One match per skill is enough

    return matches


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Non-blocking on error

    prompt = input_data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    skills = load_skills()
    if not skills:
        sys.exit(0)

    matches = find_matching_skills(prompt, skills)
    if not matches:
        sys.exit(0)

    # Build reminder message
    if len(matches) == 1:
        skill_name, trigger = matches[0]
        message = f"Consider using the Skill tool to invoke /{skill_name} for this task (matched: '{trigger}')"
    else:
        lines = ["Consider using the Skill tool for this task. Relevant skills:"]
        for skill_name, trigger in matches:
            lines.append(f"  - /{skill_name} (matched: '{trigger}')")
        message = "\n".join(lines)

    # Output as context for Claude (exit 0 = stdout added to context)
    print(message)
    sys.exit(0)


if __name__ == "__main__":
    main()
