---
name: compound
description: Capture solved problems as memory events for cross-session learning. Use after solving non-trivial problems. Triggers on "/compound", "document this solution", "capture this learning", "remember this fix".
---

# Knowledge Capture (/compound)

Capture what you just learned as a memory event. Future sessions will see it automatically.

## When to Use

- After debugging a non-trivial issue
- After discovering a platform-specific gotcha
- After finding a non-obvious root cause
- After trying multiple approaches and finding one that works

## Workflow

### Step 1: Extract the Learning

Review the current session. Write a **1-5 sentence summary** of what was learned. Focus on:
- What was the problem?
- What was the root cause?
- What fixed it?
- What should future sessions know?

### Step 2: Extract Entities

Identify 3-10 entity tags — file paths, concept names, tool names, platform names. These are search keys for future retrieval.

### Step 3: Write the Event

Run this command to write the event (replace the content and entities):

```bash
cd {project_root} && python3 -c "
import sys; sys.path.insert(0, 'config/hooks')
from _memory import append_event
path = append_event(
    cwd='$(pwd)',
    content='''YOUR LEARNING SUMMARY HERE''',
    entities=['entity1', 'entity2', 'entity3'],
    event_type='compound',
    source='compound',
    meta={'session_context': 'brief description of what task triggered this'}
)
print(f'Event captured: {path.name}')
"
```

### Step 4: Confirm

After writing, confirm:

```
Memory captured: evt_{timestamp}.json

Entities: [list]

Future sessions will see this automatically via compound-context-loader.
```

## Example

After discovering that `ps -o comm=` returns different formats on macOS vs Linux:

```bash
python3 -c "
import sys; sys.path.insert(0, 'config/hooks')
from _memory import append_event
append_event(
    cwd='$(pwd)',
    content='ps -o comm= returns full path on Linux but name-only on macOS. basename() on a name without separators strips incorrectly. Use session_id isolation instead of PID-based process detection.',
    entities=['_common.py', 'hooks', 'macOS', 'Linux', 'platform-portability', 'ps', 'basename'],
    event_type='compound',
    source='compound',
    meta={'session_context': 'debugging PID-scoped state isolation failure on macOS'}
)
print('Event captured.')
"
```

## Auto-Capture

Most learnings are captured **automatically** by the stop hook — no /compound needed. The stop hook archives completion checkpoint data as a memory event on every successful stop.

Use /compound only for **deep captures** where the auto-captured summary isn't enough detail.

## Integration

- **SessionStart**: compound-context-loader.py injects top 5 relevant events
- **Stop**: stop-validator.py auto-captures checkpoint as event
- **Manual**: /compound for detailed captures
- **Search**: `grep -riwl "keyword" ~/.claude/memory/*/events/`
