# Stop Quality Agent Hook

Agent-type Stop hook that reads the session transcript and evaluates whether the
completion checkpoint honestly represents the work done.

## Architecture

```
Stop event fires
  │
  ├─► [1] stop-validator.py (command hook, 10s)
  │   Deterministic field validation: is_job_complete, what_was_done,
  │   key_insight, search_terms, linters_pass. Blocks if fields are wrong.
  │   Also captures memory event on success.
  │
  └─► [2] stop-quality-agent (agent hook, 90s)
      Transcript-based judgment: reads checkpoint + transcript tail,
      evaluates honesty. Only runs substantive evaluation for autonomous
      sessions. Casual sessions get fast-path ok:true.
```

The command hook handles **structure** (are the fields filled in correctly?).
The agent hook handles **substance** (is the content honest?).

This is the Kambhampati insight: deterministic validation for hard gates,
a separate model instance for judgment calls. The agent hook is a different
model with no context momentum — it evaluates from a clean perspective.

## What it checks

1. **Honest what_was_done** — Does the transcript show the claimed work actually happened?
   Look for Edit/Write/Bash tool calls that match the claims.

2. **Genuine key_insight** — Is the key_insight a transferable lesson, or just a
   restatement of what_was_done? A lesson teaches something reusable about a
   class of problems. A restatement just describes what happened this time.

3. **No incomplete work** — Are there unresolved errors, TODOs, or "I'll do this later"
   statements in the transcript tail?

## Fast path

Non-autonomous sessions (no `.claude/autonomous-state.json`) get `{"ok": true}`
immediately. The evaluation is only valuable for autonomous sessions where the
agent has been working independently.

## Configuration

Registered in `config/settings.json` as the second hook in the Stop array:

```json
{
  "type": "agent",
  "prompt": "...",
  "timeout": 90
}
```

The prompt is inline in settings.json. This file is reference documentation.

## Tuning

- **Timeout**: 90s. Should complete in 15-30s typically (3-5 tool calls).
- **Model**: Default (Haiku). Fast and cheap; quality evaluation doesn't
  need Opus-level reasoning.
- **False positive rate**: Designed to be LOW. The prompt says "if in doubt,
  allow." A false positive (blocking good work) wastes the user's time.
  A false negative (allowing bad work) just means a slightly lower-quality
  memory event gets captured.
