# Session Memories

## Architectural Decisions

### Status File Enforcement (2026-01-09)
**Decision**: Status.md verification happens at Stop time AND is NOT bypassed by `stop_hook_active`.

**Why**: Advisory hooks (exit 0) on UserPromptSubmit are easily ignored when Claude focuses on user tasks. The Stop hook is the only reliable enforcement point because it blocks action. By checking status freshness even on the second stop attempt, Claude cannot bypass the status requirement regardless of the compliance checklist.

**Implementation**:
- `status-working.py` (UserPromptSubmit) - reminds Claude to update status
- `stop-validator.py` (Stop) - blocks if status.md missing or older than 5 minutes
- Status check runs BEFORE `stop_hook_active` bypass check
