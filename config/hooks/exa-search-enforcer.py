#!/usr/bin/env python3
"""
PreToolUse hook to remind agents to use Exa MCP instead of WebSearch.

Soft enforcement: when WebSearch is invoked, injects additionalContext
reminding that Exa MCP tools are preferred. Does NOT block the tool call.

Hook event: PreToolUse
Matcher: WebSearch

Exit codes:
  0 - Always allows (soft enforcement via additionalContext only)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add hooks directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))
from _common import log_debug

REMINDER = (
    "REMINDER: Exa MCP is the preferred search tool. "
    "If Exa tools are not yet loaded, use ToolSearch(query: 'exa') to discover them. "
    "Use `web_search_exa` for technical research, "
    "`get_code_context_exa` for GitHub/code search, and "
    "`company_research_exa` for vendor research. "
    "Only use WebSearch as a fallback if Exa MCP tools are unavailable in this session."
)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    if tool_name != "WebSearch":
        sys.exit(0)

    log_debug(
        "WebSearch invoked, injecting Exa reminder",
        hook_name="exa-search-enforcer",
        parsed_data={"tool_name": tool_name},
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
