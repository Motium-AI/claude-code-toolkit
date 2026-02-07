#!/usr/bin/env python3
"""
SubagentStart hook: inject Exa MCP preference into all subagents.

PreToolUse hooks don't fire inside subagents, so WebSearch can't be
blocked there. Instead, this hook injects additionalContext into every
subagent telling it to use Exa MCP tools instead of WebSearch.

Hook event: SubagentStart
Matcher: (none — fires for all subagent types)
"""

from __future__ import annotations

import json
import sys


CONTEXT = (
    "IMPORTANT: Do NOT use the built-in WebSearch tool. "
    "Use Exa MCP tools instead:\n"
    "- web_search_exa (general web search)\n"
    "- get_code_context_exa (code/GitHub/docs search)\n"
    "- company_research_exa (company/vendor info)\n"
    "If Exa tools aren't visible, use ToolSearch(query: 'exa') to discover them."
)


def main():
    sys.stdin.read()

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": CONTEXT,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
