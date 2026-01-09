#!/usr/bin/env python3
"""
UserPromptSubmit hook - instructs Claude to update status.md for Mimesis UI monitoring.

Uses strong language to ensure compliance. The status file is required for the
Mimesis monitoring dashboard to show session status/goals.

Exit codes:
  0 - Advisory only (does not block)
"""
import json
import sys
from datetime import datetime, timezone


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    if not cwd:
        sys.exit(0)

    timestamp = datetime.now(timezone.utc).isoformat()

    instruction = f"""<system-reminder>
Write your current status to {cwd}/.claude/status.md in this format:

```markdown
---
status: working
updated: {timestamp}
task: <brief description of what you're working on>
---

## Summary
<1-2 sentence summary of current activity>
```

Update this file periodically as you work, especially when:
- Starting a new subtask
- Encountering blockers
- Completing significant milestones
</system-reminder>"""

    print(instruction)
    sys.exit(0)


if __name__ == "__main__":
    main()
