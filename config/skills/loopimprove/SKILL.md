---
name: loopimprove
description: Simple iteration loop. Applies a prompt N times without scoring or targeting. Use for "/loopimprove" or "loop improve X".
---

# /loopimprove

Apply a prompt N times. No rubrics. No scoring. Just iterate.

## Usage

```
/loopimprove <prompt> [N]
```

- `<prompt>` - What to do each iteration (required)
- `[N]` - Number of iterations (default: 3, max: 10)

Examples:
- `/loopimprove improve the button styling 5`
- `/loopimprove make the code more readable` (3 iterations)
- `/loopimprove refactor for clarity 2`

## Behavior

1. Parse prompt and N from input (N defaults to 3, capped at 10)
2. For each iteration 1..N:
   - Show: `--- Iteration i/N ---`
   - Apply the prompt
   - Summarize what changed
3. Show final summary
4. Write checkpoint and stop

## Checkpoint (3+1)

```json
{
  "self_report": {
    "is_job_complete": true,
    "code_changes_made": true,
    "linters_pass": true,
    "linters_pass_at_version": "abc1234",
    "category": "refactor"
  },
  "reflection": {
    "what_was_done": "Ran N iterations of '<prompt>'",
    "what_remains": "none",
    "key_insight": "...",
    "search_terms": ["loopimprove", ...]
  }
}
```

## Triggers

- `/loopimprove`
- "loop improve"
- "iterate N times"
