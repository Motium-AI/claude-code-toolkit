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

### Step 1: Extract the Learning (LESSON-first)

Review the current session. Structure the content with LESSON first — this is what future sessions see even if truncated:

```
LESSON: <the reusable insight — what should future sessions know? 1 sentence>
PROBLEM: <what happened>
CAUSE: <root cause>
FIX: <what resolved it>
```

### Step 2: Extract Entities

Identify 5-12 entity tags — **concept keywords first**, then file paths. These are search keys for future retrieval.

**Concept keywords** (PRIMARY — match across different file contexts):
- Tool names: `maestro`, `mcp`, `ruff`
- Error types: `stdout-pollution`, `json-rpc-corruption`
- Technique names: `atomic-write`, `crash-safety`
- Platform names: `macOS`, `linux`

**File paths** (SECONDARY — match when touching the same files):
- Parent/base: `hooks/_memory.py`
- Basename: `_memory.py`

### Step 3: Pick a Category

Choose the most fitting category for the learning:
- `bugfix` — fixed a bug, root cause found
- `gotcha` — platform quirk, non-obvious behavior
- `architecture` — design decision, structural insight
- `pattern` — reusable solution pattern
- `config` — configuration, environment, setup
- `refactor` — code restructuring, cleanup

### Step 4: Write the Event

Run this command to write the event (replace the content and entities):

```bash
cd {project_root} && python3 -c "
import sys; sys.path.insert(0, 'config/hooks')
from _memory import append_event
path = append_event(
    cwd='$(pwd)',
    content='''LESSON: <1 sentence insight>
PROBLEM: <what happened>
CAUSE: <root cause>
FIX: <what resolved it>''',
    entities=['macOS', 'platform-portability', 'process-detection', '_common.py', 'hooks/_common.py'],
    event_type='compound',
    source='compound',
    category='gotcha',
    meta={'session_context': 'brief description'}
)
print(f'Event captured: {path.name}' if path else 'Skipped (duplicate)')
"
```

### Step 5: Confirm

After writing, confirm:

```
Memory captured: evt_{timestamp}.json

Category: gotcha
Entities: [concept keywords + file paths]

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
    content='''LESSON: Never assume Unix command output format is consistent across platforms.
PROBLEM: ps -o comm= returns full path on Linux but name-only on macOS.
CAUSE: macOS and Linux have different ps implementations with incompatible output formats.
FIX: Use session_id isolation instead of PID-based process detection.''',
    entities=['macOS', 'linux', 'platform-portability', 'process-detection', 'ps-command', '_common.py', 'hooks/_common.py'],
    event_type='compound',
    source='compound',
    category='gotcha',
    meta={'session_context': 'debugging PID-scoped state isolation failure on macOS'}
)
print('Event captured.')
"
```

## Auto-Capture (v3)

Most learnings are captured **automatically** by the stop hook — no /compound needed.

The checkpoint template now requires:
- **`key_insight`** (>30 chars): the reusable lesson — what you LEARNED, not what you did
- **`search_terms`** (2-7 items): concept keywords for memory retrieval
- **`category`**: bugfix | gotcha | architecture | pattern | config | refactor

The stop hook archives these as a structured memory event with concept-first entities.

Use /compound only for **deep captures** where the auto-captured summary isn't enough detail (e.g., multi-step root cause analysis, failed approaches worth documenting).

## Integration

- **SessionStart**: compound-context-loader.py injects top 10 relevant events as structured XML
- **Stop**: stop-validator.py auto-captures checkpoint (LESSON-first) with concept entities
- **Manual**: /compound for detailed captures
- **Scoring**: 4-signal (entity overlap 35%, recency 30%, content quality 20%, source 15%)
- **Search**: `grep -riwl "keyword" ~/.claude/memory/*/events/`
